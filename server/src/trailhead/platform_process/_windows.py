"""Windows process-tree management backed by a Job Object."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path
import subprocess
from typing import cast

from ._protocol import ManagedProcess

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
        try:
            self.close()
        except Exception:
            pass


class _WindowsProcess:
    """A process and the Windows Job Object containing its descendants."""

    def __init__(self, process: subprocess.Popen[bytes], job: _WindowsJob) -> None:
        self.process = process
        self._job: _WindowsJob | None = job
        self._terminated = False

    def terminate_tree(self) -> None:
        """Terminate the process's Job Object, with an exact-process fallback."""

        if self._terminated:
            return
        self._terminated = True

        job = self._job
        self._job = None
        if job is not None:
            try:
                job.terminate()
                return
            except OSError:
                # Closing a KILL_ON_JOB_CLOSE job in terminate() normally
                # succeeded even if TerminateJobObject reported a race.
                pass

        if self.process.poll() is None:
            try:
                self.process.kill()
            except OSError:
                pass


def _stop_failed_process(process: subprocess.Popen[bytes]) -> None:
    """Reap a process whose isolated startup could not be completed."""

    try:
        process.kill()
    except OSError:
        pass
    finally:
        process.wait()


def open_process(
    command: tuple[str, ...], cwd: Path, environment: dict[str, str]
) -> ManagedProcess:
    """Open a suspended child, assign it to a Job Object, then resume it."""

    creation_flags = (
        int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP")) | _CREATE_SUSPENDED
    )
    job = _WindowsJob()
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
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
        _stop_failed_process(process)
        raise RuntimeError(
            "Windows prevented Trailhead from assigning the student "
            "process to an isolated Job Object"
        ) from error

    try:
        job.resume_process(process.pid)
    except BaseException:
        job.close()
        _stop_failed_process(process)
        raise

    return _WindowsProcess(process, job)
