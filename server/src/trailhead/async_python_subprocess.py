"""Run user Python modules without blocking Trailhead's asyncio event loop."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import subprocess
import sys
from typing import BinaryIO, cast

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from .platform_process import ManagedProcess, open_process
from .project import get_project_root
from .web_socket_event import WebSocketEvent

TEN_MEGABYTES: int = 10 * 1024 * 1024
_PROMPT_PREFIX = b"\xff\xff\xff\xff"
_TRAILHEAD_PACKAGE_ROOT = Path(__file__).resolve().parent
_TRAILHEAD_IMPORT_ROOT = _TRAILHEAD_PACKAGE_ROOT.parent
_CHILD_BOOTSTRAP = _TRAILHEAD_PACKAGE_ROOT / "_child_bootstrap.py"


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
        self._managed_process: ManagedProcess | None = None
        self._termination_requested = False
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
            "-P",
            str(_CHILD_BOOTSTRAP),
            self._wrapper,
            self._module,
        )

    async def start(self) -> int:
        """Start the child through the host's process-tree implementation."""

        if self._process is not None:
            raise RuntimeError("Process has already been started")

        environment = os.environ.copy()
        # A stable encoding is important because output crosses a JSON/WebSocket
        # boundary.
        environment["PYTHONIOENCODING"] = "utf-8"
        environment["PYTHONUTF8"] = "1"
        # The server may have been imported through debugger-managed sys.path
        # state which a fresh child does not inherit. Also, without -P, Python
        # searches the student's project before the installed Trailhead package,
        # so a project package named `trailhead` can shadow our wrappers.
        python_path = environment.get("PYTHONPATH")
        import_paths = [str(_TRAILHEAD_IMPORT_ROOT), str(self._project_root)]
        if python_path:
            import_paths.append(python_path)
        environment["PYTHONPATH"] = os.pathsep.join(import_paths)

        # Native process startup is blocking, so keep it off the event loop.
        open_task = asyncio.create_task(
            asyncio.to_thread(self._open_process, environment)
        )
        try:
            managed_process = await asyncio.shield(open_task)
        except asyncio.CancelledError:
            # to_thread cannot stop an in-flight Popen. Take ownership of its
            # eventual result before propagating cancellation so no child leaks.
            managed_process = await open_task
            self._managed_process = managed_process
            self._process = managed_process.process
            self.kill()
            await asyncio.to_thread(managed_process.process.wait)
            raise
        self._managed_process = managed_process
        process = managed_process.process
        self._process = process

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

    def _open_process(self, environment: dict[str, str]) -> ManagedProcess:
        """Open an isolated process tree using the host's implementation."""

        return open_process(self.command, self._project_root, environment)

    def _terminate_process_tree(self) -> None:
        """Terminate the isolated tree allocated by ``start``."""

        managed_process = self._managed_process
        if managed_process is not None:
            managed_process.terminate_tree()

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
