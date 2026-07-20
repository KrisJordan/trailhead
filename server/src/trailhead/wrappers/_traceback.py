"""Build portable JSON traceback payloads for Trailhead's child wrappers."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
import sys
import sysconfig
import traceback
from typing import Any

_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_STDLIB_ROOTS = tuple(
    Path(path).resolve()
    for name in ("stdlib", "platstdlib")
    if (path := sysconfig.get_path(name))
)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except (ValueError, OSError):
        return False


def _is_internal(filename: str) -> bool:
    if filename.startswith(("<frozen importlib", "<frozen runpy")):
        return True
    if filename.startswith("<"):
        return False

    path = Path(filename).resolve()
    if _is_relative_to(path, _PACKAGE_ROOT):
        return True
    return any(_is_relative_to(path, stdlib_root) for stdlib_root in _STDLIB_ROOTS)


def display_filename(filename: str, root: Path | None = None) -> str:
    """Format a traceback filename relative to the project when possible."""

    if filename.startswith("<"):
        return filename
    path = Path(filename).resolve()
    project_root = (root or Path.cwd()).resolve()
    try:
        return path.relative_to(project_root).as_posix()
    except (ValueError, OSError):
        return str(path)


def exception_payload(error: BaseException) -> dict[str, Any]:
    """Serialize an exception without Docker- or Unix-specific path rules."""

    summaries = traceback.extract_tb(error.__traceback__)
    frame_infos = inspect.getinnerframes(error.__traceback__)  # type: ignore[arg-type]
    stack_trace: list[dict[str, Any]] = []

    for summary, frame_info in zip(summaries, frame_infos):
        if _is_internal(summary.filename):
            continue

        local_values: dict[str, Any] = {}
        for name, value in frame_info.frame.f_locals.items():
            try:
                json.dumps(value)
                local_values[name] = value
            except (TypeError, OverflowError, ValueError):
                local_values[name] = "[See value in Debugger]"

        stack_trace.append(
            {
                "filename": display_filename(summary.filename),
                "lineno": summary.lineno,
                "name": summary.name,
                "line": "".join(frame_info.code_context or []),
                "end_lineno": summary.end_lineno,
                "colno": summary.colno,
                "end_colno": summary.end_colno,
                "locals": local_values,
            }
        )

    return {
        "type": type(error).__name__,
        "message": str(error),
        "stack_trace": stack_trace,
    }


def emit_exception(error: BaseException) -> None:
    """Write one JSON exception record to the wrapper's stderr stream."""

    sys.stderr.write(json.dumps(exception_payload(error)) + "\n")
    sys.stderr.flush()
