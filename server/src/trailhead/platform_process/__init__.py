"""Select Trailhead's native process-tree implementation."""

from __future__ import annotations

from pathlib import Path
import sys

from ._protocol import ManagedProcess

__all__ = ["ManagedProcess", "open_process"]


def open_process(
    command: tuple[str, ...], cwd: Path, environment: dict[str, str]
) -> ManagedProcess:
    """Open an isolated child process using the current host's mechanism."""

    if sys.platform == "win32":
        from ._windows import open_process as open_windows_process

        return open_windows_process(command, cwd, environment)

    from ._posix import open_process as open_posix_process

    return open_posix_process(command, cwd, environment)
