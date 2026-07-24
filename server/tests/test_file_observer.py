from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from watchdog.events import DirModifiedEvent, FileModifiedEvent, FileMovedEvent

from trailhead import file_observer
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


async def test_file_events_use_project_relative_posix_paths(tmp_path: Path) -> None:
    events: list[WebSocketEvent] = []

    async def notify(event: WebSocketEvent) -> None:
        events.append(event)

    source = tmp_path / "package" / "test_example.py"
    destination = tmp_path / "package" / "test_renamed.py"
    handler = _FileChangeHandler(
        notify,
        asyncio.get_running_loop(),
        tmp_path,
    )

    handler.on_moved(FileMovedEvent(str(source), str(destination)))
    for _ in range(10):
        if events:
            break
        await asyncio.sleep(0)

    assert events == [
        WebSocketEvent(
            type="file_moved",
            data={
                "path": "./package/test_example.py",
                "dest_path": "./package/test_renamed.py",
            },
        )
    ]


async def test_move_filter_detects_python_source_or_destination() -> None:
    async def notify(event: WebSocketEvent) -> None:
        pass

    handler = _FileChangeHandler(notify, asyncio.get_running_loop())

    assert handler._event_filter(FileMovedEvent("notes.txt", "test_notes.py"))
    assert handler._event_filter(FileMovedEvent("test_old.py", "notes.txt"))
    assert not handler._event_filter(FileMovedEvent("notes.txt", "notes.md"))


async def test_duplicate_filter_allows_a_distinct_save_after_debounce_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def notify(event: WebSocketEvent) -> None:
        pass

    now = 100.0
    monkeypatch.setattr(file_observer.time, "time", lambda: now)
    handler = _FileChangeHandler(notify, asyncio.get_running_loop())
    event = FileModifiedEvent("test_example.py")

    assert handler._event_filter(event)
    now += 0.05
    assert not handler._event_filter(event)
    now += 0.06
    assert handler._event_filter(event)
