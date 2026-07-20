"""Run user Python modules without blocking Trailhead's asyncio event loop."""

from __future__ import annotations

import asyncio
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import signal
import subprocess
import sys
from typing import BinaryIO, cast

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from .project import get_project_root
from .web_socket_event import WebSocketEvent

TEN_MEGABYTES: int = 10 * 1024 * 1024
_PROMPT_PREFIX = b"\xff\xff\xff\xff"

_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
_PROCESS_TERMINATE = 0x0001
_PROCESS_SET_QUOTA = 0x0100
_CREATE_SUSPENDED = 0x00000004
_TH32CS_SNAPTHREAD = 0x00000004
_THREAD_SUSPEND_RESUME = 0x0002
_INVALID_DWORD = 0xFFFFFFFF
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class _JobObjectBasicLimitInformation(ctypes.Structure):
    """Windows ``JOBOBJECT_BASIC_LIMIT_INFORMATION`` structure."""

    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IoCounters(ctypes.Structure):
    """Windows ``IO_COUNTERS`` structure."""

    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _JobObjectExtendedLimitInformation(ctypes.Structure):
    """Windows ``JOBOBJECT_EXTENDED_LIMIT_INFORMATION`` structure."""

    _fields_ = [
        ("BasicLimitInformation", _JobObjectBasicLimitInformation),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _ThreadEntry32(ctypes.Structure):
    """Windows ``THREADENTRY32`` structure used to resume a suspended child."""

    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ThreadID", wintypes.DWORD),
        ("th32OwnerProcessID", wintypes.DWORD),
        ("tpBasePri", wintypes.LONG),
        ("tpDeltaPri", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
    ]


def _last_windows_error() -> OSError:
    """Build an ``OSError`` without importing Windows-only ctypes names."""

    get_last_error = getattr(ctypes, "get_last_error")
    win_error = getattr(ctypes, "WinError")
    return cast(OSError, win_error(get_last_error()))


class _WindowsJob:
    """Own a Windows Job Object that terminates every assigned descendant."""

    def __init__(self) -> None:
        win_dll = getattr(ctypes, "WinDLL")
        self._kernel32 = win_dll("kernel32", use_last_error=True)
        self._handle: int | None = None

        create_job = self._kernel32.CreateJobObjectW
        create_job.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
        create_job.restype = wintypes.HANDLE
        handle = create_job(None, None)
        if not handle:
            raise _last_windows_error()
        self._handle = int(handle)

        limits = _JobObjectExtendedLimitInformation()
        limits.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        set_information = self._kernel32.SetInformationJobObject
        set_information.argtypes = (
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        )
        set_information.restype = wintypes.BOOL
        if not set_information(
            self._handle,
            _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
            ctypes.byref(limits),
            ctypes.sizeof(limits),
        ):
            error = _last_windows_error()
            self.close()
            raise error

    def assign(self, pid: int) -> None:
        """Assign a process, and therefore its future children, to this job."""

        if self._handle is None:
            raise RuntimeError("Windows Job Object has already been closed")

        open_process = self._kernel32.OpenProcess
        open_process.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        open_process.restype = wintypes.HANDLE
        process_handle = open_process(
            _PROCESS_TERMINATE | _PROCESS_SET_QUOTA, False, pid
        )
        if not process_handle:
            raise _last_windows_error()

        try:
            assign_process = self._kernel32.AssignProcessToJobObject
            assign_process.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
            assign_process.restype = wintypes.BOOL
            if not assign_process(self._handle, process_handle):
                raise _last_windows_error()
        finally:
            self._close_handle(int(process_handle))

    def terminate(self) -> None:
        """Terminate the whole job and release its operating-system handle."""

        handle = self._handle
        if handle is None:
            return
        try:
            terminate_job = self._kernel32.TerminateJobObject
            terminate_job.argtypes = (wintypes.HANDLE, wintypes.UINT)
            terminate_job.restype = wintypes.BOOL
            if not terminate_job(handle, 1):
                raise _last_windows_error()
        finally:
            # KILL_ON_JOB_CLOSE is a second line of defence if explicit
            # termination failed or raced with the root process exiting.
            self.close()

    def resume_process(self, pid: int) -> None:
        """Resume the primary thread of a process created suspended."""

        create_snapshot = self._kernel32.CreateToolhelp32Snapshot
        create_snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
        create_snapshot.restype = wintypes.HANDLE
        snapshot = create_snapshot(_TH32CS_SNAPTHREAD, 0)
        if not snapshot or int(snapshot) == _INVALID_HANDLE_VALUE:
            raise _last_windows_error()

        try:
            entry = _ThreadEntry32()
            entry.dwSize = ctypes.sizeof(entry)
            thread_first = self._kernel32.Thread32First
            thread_first.argtypes = (wintypes.HANDLE, ctypes.POINTER(_ThreadEntry32))
            thread_first.restype = wintypes.BOOL
            thread_next = self._kernel32.Thread32Next
            thread_next.argtypes = (wintypes.HANDLE, ctypes.POINTER(_ThreadEntry32))
            thread_next.restype = wintypes.BOOL

            has_entry = bool(thread_first(snapshot, ctypes.byref(entry)))
            while has_entry:
                if entry.th32OwnerProcessID == pid:
                    self._resume_thread(entry.th32ThreadID)
                    return
                has_entry = bool(thread_next(snapshot, ctypes.byref(entry)))
        finally:
            self._close_handle(int(snapshot))

        raise RuntimeError(f"Unable to find the suspended Windows process {pid}")

    def _resume_thread(self, thread_id: int) -> None:
        open_thread = self._kernel32.OpenThread
        open_thread.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        open_thread.restype = wintypes.HANDLE
        thread_handle = open_thread(_THREAD_SUSPEND_RESUME, False, thread_id)
        if not thread_handle:
            raise _last_windows_error()

        try:
            resume_thread = self._kernel32.ResumeThread
            resume_thread.argtypes = (wintypes.HANDLE,)
            resume_thread.restype = wintypes.DWORD
            if resume_thread(thread_handle) == _INVALID_DWORD:
                raise _last_windows_error()
        finally:
            self._close_handle(int(thread_handle))

    def close(self) -> None:
        """Release the job; KILL_ON_JOB_CLOSE also ends any remaining members."""

        handle = self._handle
        if handle is None:
            return
        self._handle = None
        self._close_handle(handle)

    def _close_handle(self, handle: int) -> None:
        close_handle = self._kernel32.CloseHandle
        close_handle.argtypes = (wintypes.HANDLE,)
        close_handle.restype = wintypes.BOOL
        close_handle(handle)

    def __del__(self) -> None:
        # Also release the native handle if start() is cancelled while its
        # thread-backed Popen call is finishing.
        try:
            self.close()
        except Exception:
            pass


class AsyncPythonSubprocess:
    """A Python child process whose standard streams are relayed over a socket."""

    def __init__(
        self,
        module: str,
        client: WebSocket,
        wrapper: str = "trailhead.wrappers.module",
        project_root: Path | None = None,
    ):
        self._module = module
        self._client = client
        self._wrapper = wrapper
        self._project_root = (project_root or get_project_root()).resolve()
        self._process: subprocess.Popen[bytes] | None = None
        self._windows_job: _WindowsJob | None = None
        self._termination_requested = False
        self._process_tree_terminated = False
        self._stdout_pipe_task: asyncio.Task[None] | None = None
        self._stderr_pipe_task: asyncio.Task[None] | None = None
        self._exit_task: asyncio.Task[None] | None = None

    @property
    def command(self) -> tuple[str, ...]:
        """The argv used for the child, exposed for diagnostics and tests."""

        if not sys.executable:
            raise RuntimeError("Unable to determine the current Python interpreter")
        return (
            sys.executable,
            "-u",
            "-m",
            self._wrapper,
            self._module,
        )

    async def start(self) -> int:
        """Start the child using asyncio's cross-platform subprocess transport."""

        if self._process is not None:
            raise RuntimeError("Process has already been started")

        environment = os.environ.copy()
        # A stable encoding is important because output crosses a JSON/WebSocket
        # boundary and Windows otherwise inherits a locale-dependent code page.
        environment["PYTHONIOENCODING"] = "utf-8"
        environment["PYTHONUTF8"] = "1"

        # Uvicorn's reload worker uses a SelectorEventLoop on Windows, where
        # asyncio's subprocess transport is unavailable. Popen plus thread-backed
        # I/O works with every asyncio event loop on all three supported hosts.
        open_task = asyncio.create_task(
            asyncio.to_thread(self._open_process, environment)
        )
        try:
            process, windows_job = await asyncio.shield(open_task)
        except asyncio.CancelledError:
            # to_thread cannot stop an in-flight Popen. Take ownership of its
            # eventual result before propagating cancellation so no child leaks.
            process, windows_job = await open_task
            self._process = process
            self._windows_job = windows_job
            self.kill()
            await asyncio.to_thread(process.wait)
            raise
        self._process = process
        self._windows_job = windows_job

        if process.stdout is None or process.stderr is None:
            self.kill()
            raise RuntimeError("Unable to connect to the child process output")

        stdout = cast(BinaryIO, process.stdout)
        stderr = cast(BinaryIO, process.stderr)
        self._stdout_pipe_task = asyncio.create_task(self._stdout_pipe(stdout))
        self._stderr_pipe_task = asyncio.create_task(self._stderr_pipe(stderr))
        self._exit_task = asyncio.create_task(self._exit())
        if self._termination_requested or not self.client_connected():
            self._terminate_process_tree()
        return process.pid

    async def await_end(self) -> int:
        """Wait for the child and all output relay tasks to finish."""

        if self._process is None or self._exit_task is None:
            raise RuntimeError("Process has not been started")
        await self._exit_task
        if self._process.returncode is None:
            raise RuntimeError("Child exited without a return code")
        return self._process.returncode

    def subprocess_exited(self) -> bool:
        """Return whether the child has a return code."""

        return self._process is not None and self._process.poll() is not None

    def client_connected(self) -> bool:
        return self._client.client_state == WebSocketState.CONNECTED

    async def write(self, data: str) -> None:
        """Write one line of UTF-8 input to the child."""

        process = self._process
        if process is None or process.stdin is None or self.subprocess_exited():
            return
        if not data.endswith("\n"):
            data += "\n"
        try:
            await asyncio.to_thread(
                self._write_stdin,
                cast(BinaryIO, process.stdin),
                data.encode("utf-8"),
            )
        except (BrokenPipeError, ConnectionResetError, OSError, ValueError):
            # The child can exit between the return-code check and the write.
            return

    def kill(self) -> None:
        """Immediately terminate the child and every process it spawned."""

        self._termination_requested = True
        self._terminate_process_tree()

    def _open_process(
        self, environment: dict[str, str]
    ) -> tuple[subprocess.Popen[bytes], _WindowsJob | None]:
        """Open an isolated process tree using the host's native mechanism."""

        if sys.platform == "win32":
            # A Job Object supplies Windows' reliable process-tree lifetime
            # boundary. The child starts suspended so it cannot create an
            # unassigned descendant in the interval before job assignment.
            creation_flags = (
                int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP")) | _CREATE_SUSPENDED
            )
            job = _WindowsJob()
            try:
                process = subprocess.Popen(
                    self.command,
                    cwd=self._project_root,
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    bufsize=0,
                    creationflags=creation_flags,
                )
            except BaseException:
                job.close()
                raise

            try:
                job.assign(process.pid)
            except OSError as error:
                job.close()
                self._stop_failed_process(process)
                raise RuntimeError(
                    "Windows prevented Trailhead from assigning the student "
                    "process to an isolated Job Object"
                ) from error

            try:
                job.resume_process(process.pid)
            except BaseException:
                job.close()
                self._stop_failed_process(process)
                raise
            return (process, job)

        process = subprocess.Popen(
            self.command,
            cwd=self._project_root,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            bufsize=0,
            start_new_session=True,
        )
        return (process, None)

    @staticmethod
    def _stop_failed_process(process: subprocess.Popen[bytes]) -> None:
        """Reap a process whose isolated startup could not be completed."""

        try:
            process.kill()
        except OSError:
            pass
        finally:
            process.wait()

    def _terminate_process_tree(self) -> None:
        """Terminate the exact job/process group allocated by ``start``."""

        process = self._process
        if process is None or self._process_tree_terminated:
            return
        self._process_tree_terminated = True

        if sys.platform == "win32":
            job = self._windows_job
            self._windows_job = None
            if job is not None:
                try:
                    job.terminate()
                    return
                except OSError:
                    # Closing a KILL_ON_JOB_CLOSE job in terminate() normally
                    # succeeded even if TerminateJobObject reported a race.
                    pass
            if process.poll() is None:
                try:
                    process.kill()
                except OSError:
                    pass
            return

        try:
            # start_new_session made the root PID the process-group ID. Unlike
            # Popen.kill(), killpg also reaches grandchildren holding our pipes.
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            # The entire group has already exited.
            pass
        except PermissionError:
            # This should not happen for our own group, but retain a safe
            # single-process fallback instead of affecting any broader target.
            if process.poll() is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass

    @staticmethod
    def _write_stdin(stdin: BinaryIO, data: bytes) -> None:
        stdin.write(data)
        stdin.flush()

    @staticmethod
    def _read_exactly(stream: BinaryIO, length: int) -> bytes:
        output = bytearray()
        while len(output) < length:
            chunk = stream.read(length - len(output))
            if not chunk:
                break
            output.extend(chunk)
        return bytes(output)

    async def _read_stdout(self, stdout: BinaryIO) -> tuple[str, bool]:
        output = await asyncio.to_thread(stdout.readline, TEN_MEGABYTES)
        is_prompt = False

        if output.startswith(_PROMPT_PREFIX):
            try:
                length = int(output[len(_PROMPT_PREFIX) :].decode("ascii"))
            except (UnicodeDecodeError, ValueError):
                return (output.decode("utf-8", errors="replace"), False)
            if not 0 <= length <= TEN_MEGABYTES:
                return (output.decode("utf-8", errors="replace"), False)
            output = await asyncio.to_thread(self._read_exactly, stdout, length)
            is_prompt = True

        return (output.decode("utf-8", errors="replace"), is_prompt)

    async def _stdout_pipe(self, stdout: BinaryIO) -> None:
        while True:
            try:
                output, is_prompt = await self._read_stdout(stdout)
                if not output or not self.client_connected():
                    break
                process = self._process
                if process is not None:
                    await self._client.send_text(
                        WebSocketEvent(
                            type="STDOUT",
                            data={
                                "pid": process.pid,
                                "data": output,
                                "is_input_prompt": is_prompt,
                            },
                        ).model_dump_json()
                    )
            except asyncio.CancelledError:
                raise
            except Exception as error:
                print(f"Unable to relay child stdout: {error}", file=sys.stderr)
                break

    async def _stderr_pipe(self, stderr: BinaryIO) -> None:
        while True:
            try:
                output = await asyncio.to_thread(stderr.readline, TEN_MEGABYTES)
                if not output or not self.client_connected():
                    break

                process = self._process
                if process is not None:
                    await self._client.send_text(
                        WebSocketEvent(
                            type="STDERR",
                            data={
                                "pid": process.pid,
                                "data": output.decode("utf-8", errors="replace"),
                            },
                        ).model_dump_json()
                    )
            except asyncio.CancelledError:
                raise
            except Exception as error:
                print(f"Unable to relay child stderr: {error}", file=sys.stderr)
                break

    async def _exit(self) -> None:
        process = self._process
        if process is None:
            return

        while process.poll() is None:
            if not self.client_connected():
                self.kill()
            await asyncio.sleep(0.05)

        # A student module can leave children running after its wrapper exits.
        # Tear down the isolation boundary before waiting for inherited pipes.
        self._terminate_process_tree()
        await asyncio.to_thread(process.wait)
        pipe_tasks = [
            task
            for task in (self._stdout_pipe_task, self._stderr_pipe_task)
            if task is not None
        ]
        if pipe_tasks:
            await asyncio.gather(*pipe_tasks)

        if self.client_connected():
            await self._client.send_text(
                WebSocketEvent(
                    type="EXIT",
                    data={"pid": process.pid, "returncode": process.returncode},
                ).model_dump_json()
            )
