"""Run pytest for one project module and emit structured protocol records."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any

import pytest

from trailhead.pytest_plugin import TrailheadPytestPlugin
from trailhead.pytest_protocol import (
    DEFERRED_PYTHONPATH_ENV,
    EVENT_PREFIX,
    limited_text,
)


def _emit(event_type: str, data: dict[str, Any]) -> None:
    """Write one protocol event where pytest's Python-level capture cannot hide it."""

    payload = json.dumps(
        {"type": event_type, "data": data},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    stream = sys.__stdout__
    if stream is None:
        raise RuntimeError("The pytest protocol output stream is unavailable")
    stream.write(f"{EVENT_PREFIX}{payload}\n")
    stream.flush()


def _restore_deferred_python_path() -> None:
    """Restore user import paths after trusted pytest modules are imported."""

    deferred = os.environ.pop(DEFERRED_PYTHONPATH_ENV, None)
    if deferred is None:
        return

    os.environ["PYTHONPATH"] = deferred
    project_root = Path.cwd()
    restored: list[str] = []
    for configured_path in deferred.split(os.pathsep):
        path = Path(configured_path) if configured_path else project_root
        if not path.is_absolute():
            path = project_root / path
        try:
            path = path.resolve()
        except OSError:
            path = path.absolute()
        restored.append(str(path))

    # _child_bootstrap pins Trailhead's trusted package root at sys.path[0].
    # User paths retain their original order immediately after it and ahead of
    # site-packages, matching PYTHONPATH semantics for the project under test.
    sys.path[1:1] = restored


def main() -> int:
    if len(sys.argv) < 3:
        _emit(
            "TEST_ERROR",
            {
                "kind": "protocol",
                "message": "The pytest wrapper requires a module and operation",
            },
        )
        return int(pytest.ExitCode.USAGE_ERROR)

    module_name = sys.argv[1]
    mode = sys.argv[2]
    selected_node_ids = sys.argv[3:]
    if mode not in {"collect", "run"}:
        _emit(
            "TEST_ERROR",
            {"kind": "protocol", "message": f"Unknown pytest operation: {mode}"},
        )
        return int(pytest.ExitCode.USAGE_ERROR)

    _restore_deferred_python_path()
    module_path = Path(*module_name.split(".")).with_suffix(".py").as_posix()
    targets = selected_node_ids or [module_path]
    arguments = ["--capture=sys", "--color=no", *targets]
    if mode == "collect":
        arguments.insert(0, "--collect-only")

    plugin = TrailheadPytestPlugin(
        _emit,
        mode,
        emit_collection=mode == "collect" or not selected_node_ids,
    )
    try:
        exit_code = int(pytest.main(arguments, plugins=[plugin]))
    except BaseException as error:
        message, message_truncated = limited_text(f"{type(error).__name__}: {error}")
        details, details_truncated = limited_text(repr(error))
        _emit(
            "TEST_ERROR",
            {
                "kind": "internal",
                "message": message,
                "details": details,
                "truncated": [
                    field
                    for field, truncated in (
                        ("message", message_truncated),
                        ("details", details_truncated),
                    )
                    if truncated
                ],
            },
        )
        exit_code = int(pytest.ExitCode.INTERNAL_ERROR)
    plugin.finish(exit_code)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
