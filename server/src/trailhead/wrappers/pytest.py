"""Run pytest for one project module and emit structured protocol records."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

import pytest

from trailhead.pytest_plugin import TrailheadPytestPlugin
from trailhead.pytest_protocol import EVENT_PREFIX, limited_text


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

    module_path = Path(*module_name.split(".")).with_suffix(".py").as_posix()
    targets = selected_node_ids or [module_path]
    arguments = ["--capture=sys", "--color=no", *targets]
    if mode == "collect":
        arguments.insert(0, "--collect-only")

    plugin = TrailheadPytestPlugin(_emit, mode)
    try:
        return int(pytest.main(arguments, plugins=[plugin]))
    except BaseException as error:
        details, was_truncated = limited_text(repr(error))
        _emit(
            "TEST_ERROR",
            {
                "kind": "internal",
                "message": f"{type(error).__name__}: {error}",
                "details": details,
                "truncated": ["details"] if was_truncated else [],
            },
        )
        return int(pytest.ExitCode.INTERNAL_ERROR)


if __name__ == "__main__":
    raise SystemExit(main())
