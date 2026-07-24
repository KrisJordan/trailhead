"""The platform-independent process-tree interface."""

from __future__ import annotations

import subprocess
from typing import Protocol


class ManagedProcess(Protocol):
    """A child process and the host-native boundary containing its descendants."""

    @property
    def process(self) -> subprocess.Popen[bytes]:
        """The root process whose standard streams Trailhead relays."""

        ...

    def terminate_tree(self) -> None:
        """Idempotently attempt to terminate the child and all its descendants."""

        ...
