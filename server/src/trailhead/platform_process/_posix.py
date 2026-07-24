"""POSIX process-tree management."""

from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess

from ._protocol import ManagedProcess


class _PosixProcess:
    """A process isolated in its own POSIX session and process group."""

    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        self.process = process
        self._terminated = False

    def terminate_tree(self) -> None:
        """Terminate the process group allocated when the child was opened."""

        if self._terminated:
            return
        self._terminated = True

        try:
            # start_new_session made the root PID the process-group ID. Unlike
            # Popen.kill(), killpg also reaches grandchildren holding our pipes.
            kill_process_group = getattr(os, "killpg")
            kill_signal = getattr(signal, "SIGKILL")
            kill_process_group(self.process.pid, kill_signal)
        except ProcessLookupError:
            # The entire group has already exited.
            pass
        except PermissionError:
            # This should not happen for our own group, but retain a safe
            # single-process fallback instead of affecting any broader target.
            if self.process.poll() is None:
                try:
                    self.process.kill()
                except ProcessLookupError:
                    pass


def open_process(
    command: tuple[str, ...], cwd: Path, environment: dict[str, str]
) -> ManagedProcess:
    """Open a child in a new POSIX session and process group."""

    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
        bufsize=0,
        start_new_session=True,
    )
    return _PosixProcess(process)
