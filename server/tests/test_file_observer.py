from __future__ import annotations

import asyncio

from watchdog.events import DirModifiedEvent, FileModifiedEvent

from trailhead.file_observer import _FileChangeHandler
from trailhead.web_socket_event import WebSocketEvent


async def test_file_filter_accepts_python_paths_with_windows_separators() -> None:
    async def notify(event: WebSocketEvent) -> None:
        pass

    handler = _FileChangeHandler(notify, asyncio.get_running_loop())

    assert handler._event_filter(FileModifiedEvent(r"C:\project\package\module.py"))
    assert not handler._event_filter(FileModifiedEvent(r"C:\project\.venv\module.py"))
    assert not handler._event_filter(FileModifiedEvent(r"C:\project\notes.txt"))
    assert handler._event_filter(DirModifiedEvent(r"C:\project\package"))
