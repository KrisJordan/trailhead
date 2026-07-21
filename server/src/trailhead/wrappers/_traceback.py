"""Build portable JSON traceback payloads for Trailhead's child wrappers."""

from __future__ import annotations

import inspect
import json
import linecache
from pathlib import Path
import sys
import sysconfig
import traceback
from types import FrameType
from typing import Any

_PACKAGE_ROOT = Path(__file__).resolve().parents[1]
_STDLIB_ROOTS = tuple(
    Path(path).resolve()
    for name in ("stdlib", "platstdlib")
    if (path := sysconfig.get_path(name))
)
_MAX_VALUE_LENGTH = 2_000
_MAX_REPR_LENGTH = 500


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


def _frame_module_name(frame: FrameType) -> str | None:
    spec = frame.f_globals.get("__spec__")
    spec_name = getattr(spec, "name", None)
    if isinstance(spec_name, str):
        return spec_name

    global_name = frame.f_globals.get("__name__")
    return global_name if isinstance(global_name, str) else None


def _belongs_to_module(frame: FrameType, module_name: str) -> bool:
    frame_module = _frame_module_name(frame)
    return frame_module in (module_name, f"{module_name}.__main__")


def _safe_repr(value: Any) -> str:
    try:
        rendered = repr(value)
    except Exception as error:
        rendered = f"<repr failed: {type(error).__name__}>"
    if len(rendered) > _MAX_REPR_LENGTH:
        return rendered[: _MAX_REPR_LENGTH - 1] + "\N{HORIZONTAL ELLIPSIS}"
    return rendered


def _serialize_local(value: Any) -> Any:
    try:
        encoded = json.dumps(value, allow_nan=False)
    except (TypeError, OverflowError, ValueError, RecursionError):
        encoded = None

    if encoded is not None and len(encoded) <= _MAX_VALUE_LENGTH:
        return value
    return {"type": type(value).__name__, "repr": _safe_repr(value)}


def _frame_locals(frame: FrameType) -> dict[str, Any]:
    return {
        name: _serialize_local(value)
        for name, value in frame.f_locals.items()
        if not (name.startswith("__") and name.endswith("__"))
    }


def _syntax_frame(error: SyntaxError) -> dict[str, Any] | None:
    if not isinstance(error.filename, str) or not isinstance(error.lineno, int):
        return None

    line = error.text or linecache.getline(error.filename, error.lineno)
    colno = max(error.offset - 1, 0) if isinstance(error.offset, int) else 0
    if isinstance(error.end_offset, int):
        end_colno = max(error.end_offset - 1, colno + 1)
    else:
        end_colno = colno + 1

    return {
        "filename": display_filename(error.filename),
        "lineno": error.lineno,
        "name": "<module>",
        "line": line,
        "end_lineno": error.end_lineno or error.lineno,
        "colno": colno,
        "end_colno": end_colno,
        "locals": {},
    }


def exception_payload(
    error: BaseException, *, root_module: str | None = None
) -> dict[str, Any]:
    """Serialize an exception as a student-rooted, portable traceback."""

    if error.__traceback__ is None:
        summary_frames = []
    else:
        summaries = traceback.extract_tb(error.__traceback__)
        frame_infos = inspect.getinnerframes(error.__traceback__)
        summary_frames = list(zip(summaries, frame_infos))

    if root_module is not None:
        root_index = next(
            (
                index
                for index, (_, frame_info) in enumerate(summary_frames)
                if _belongs_to_module(frame_info.frame, root_module)
            ),
            None,
        )
        if root_index is not None:
            summary_frames = summary_frames[root_index:]
        else:
            summary_frames = [
                pair for pair in summary_frames if not _is_internal(pair[0].filename)
            ]
    else:
        summary_frames = [
            pair for pair in summary_frames if not _is_internal(pair[0].filename)
        ]

    stack_trace: list[dict[str, Any]] = []

    for summary, frame_info in summary_frames:
        stack_trace.append(
            {
                "filename": display_filename(summary.filename),
                "lineno": summary.lineno,
                "name": summary.name,
                "line": "".join(frame_info.code_context or []),
                "end_lineno": summary.end_lineno,
                "colno": summary.colno,
                "end_colno": summary.end_colno,
                "locals": _frame_locals(frame_info.frame),
            }
        )

    if isinstance(error, SyntaxError):
        syntax_frame = _syntax_frame(error)
        if syntax_frame is not None and not any(
            frame["filename"] == syntax_frame["filename"]
            and frame["lineno"] == syntax_frame["lineno"]
            for frame in stack_trace
        ):
            stack_trace.append(syntax_frame)

    return {
        "type": type(error).__name__,
        "message": str(error),
        "stack_trace": stack_trace,
    }


def emit_exception(error: BaseException, *, root_module: str | None = None) -> None:
    """Write one JSON exception record to the wrapper's stderr stream."""

    sys.stderr.write(
        json.dumps(exception_payload(error, root_module=root_module), allow_nan=False)
        + "\n"
    )
    sys.stderr.flush()
