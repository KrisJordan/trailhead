"""FileObserver watches the file system for changes and makes asyncio callbacks.

It specifically is looking for changes to .py files and ignores directory changes
to some common project directories we can ignore (e.g. __pycache__, .pytest_cache, .git)

It uses a TTLCache to prevent duplicate events within half a second of each other.

Because watchdog is not asyncio compatible, we run it in a separate thread and
use run_coroutine_threadsafe to call the callback.
"""

__author__ = "Kris Jordan <kris@cs.unc.edu>"
__copyright__ = "Copyright 2023"
__license__ = "MIT"

import asyncio
import cachetools
import os
from pathlib import Path
import time
from typing import Any, Callable, Coroutine
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from .web_socket_event import WebSocketEvent
from .project import client_path

NotifierFn = Callable[[WebSocketEvent], Coroutine[Any, Any, None]]


def FileObserver(path: str | os.PathLike[str], notifier: NotifierFn) -> BaseObserver:
    """Create a file observer that watches for changes to .py files.

    Args:
        path: The path to watch for changes.
        notifier: The aysnc function to call when a change is detected.

    Returns:
        A watchdog observer instance that has started. It is the caller's responsibility
        to call stop() on the observer when it is no longer needed."""
    observer = Observer()
    root = Path(path).resolve()
    event_handler = _FileChangeHandler(notifier, asyncio.get_running_loop(), root)
    observer.schedule(event_handler, str(root), recursive=True)
    observer.start()
    return observer


class _FileChangeHandler(FileSystemEventHandler):
    def __init__(
        self,
        notifier: NotifierFn,
        loop: asyncio.AbstractEventLoop,
        root: Path | None = None,
    ):
        self._notify_func = notifier
        self._loop = loop
        self._root = root.resolve() if root is not None else None
        self._ignored_directories = {
            ".git",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            ".venv",
            "__pycache__",
            "node_modules",
            "venv",
        }
        self._cache = cachetools.TTLCache[str, float](maxsize=1000, ttl=0.1)

    def _is_relevant_path(self, path: str, is_directory: bool) -> bool:
        # Splitting both separators also makes synthetic Windows-path tests
        # meaningful when they run on a Unix CI worker (and vice versa).
        path_parts = set(path.replace("\\", "/").split("/"))
        if path_parts & self._ignored_directories:
            return False
        return is_directory or Path(path).suffix.casefold() == ".py"

    def _event_filter(self, event: FileSystemEvent):
        paths = [os.fsdecode(event.src_path)]
        destination = getattr(event, "dest_path", None)
        if destination:
            paths.append(os.fsdecode(destination))
        relevant_paths = [
            path for path in paths if self._is_relevant_path(path, event.is_directory)
        ]
        if not relevant_paths:
            return False

        cache_key = "\0".join(relevant_paths)
        current_time = time.time()
        last_time: float | None = self._cache.get(cache_key)
        if last_time is not None and current_time - last_time < self._cache.ttl:
            return False

        self._cache[cache_key] = current_time
        return True

    def _client_path(self, value: str | bytes) -> str:
        path = Path(os.fsdecode(value))
        if self._root is None:
            return path.as_posix()
        try:
            return client_path(path, self._root)
        except (OSError, ValueError):
            return path.as_posix()

    def _event_data(self, event: FileSystemEvent) -> dict[str, str]:
        data = {"path": self._client_path(event.src_path)}
        destination = getattr(event, "dest_path", None)
        if destination:
            data["dest_path"] = self._client_path(destination)
        return data

    def on_created(self, event: FileSystemEvent):
        if self._event_filter(event):
            type = "directory" if event.is_directory else "file"
            ws_event = WebSocketEvent(
                type=f"{type}_created", data=self._event_data(event)
            )
            asyncio.run_coroutine_threadsafe(self._notify_func(ws_event), self._loop)

    def on_modified(self, event: FileSystemEvent):
        if self._event_filter(event):
            type = "directory" if event.is_directory else "file"
            ws_event = WebSocketEvent(
                type=f"{type}_modified", data=self._event_data(event)
            )
            asyncio.run_coroutine_threadsafe(self._notify_func(ws_event), self._loop)

    def on_moved(self, event: FileSystemEvent):
        if self._event_filter(event):
            type = "directory" if event.is_directory else "file"
            ws_event = WebSocketEvent(
                type=f"{type}_moved", data=self._event_data(event)
            )
            asyncio.run_coroutine_threadsafe(self._notify_func(ws_event), self._loop)

    def on_deleted(self, event: FileSystemEvent):
        if self._event_filter(event):
            type = "directory" if event.is_directory else "file"
            ws_event = WebSocketEvent(
                type=f"{type}_deleted", data=self._event_data(event)
            )
            asyncio.run_coroutine_threadsafe(self._notify_func(ws_event), self._loop)
