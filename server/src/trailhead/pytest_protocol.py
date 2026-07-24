"""Shared constants and normalization helpers for the pytest child protocol."""

from __future__ import annotations

EVENT_PREFIX = "TRAILHEAD_PYTEST_EVENT:"
"""Prefix that distinguishes child protocol records from ordinary pytest output."""

DEFERRED_PYTHONPATH_ENV = "TRAILHEAD_PYTEST_DEFERRED_PYTHONPATH"
"""Carries user import paths until the trusted pytest wrapper has imported."""

MAX_NODE_ID_BYTES = 16 * 1024
"""Largest UTF-8 pytest node ID carried losslessly by the browser protocol."""

MAX_METADATA_BYTES = 16 * 1024
"""Maximum UTF-8 size of a test name, path, or combined marker list."""

MAX_OUTPUT_BYTES = 64 * 1024
"""Maximum encoded size of any user-controlled text field sent to the browser."""


def limited_text(value: object, limit: int = MAX_OUTPUT_BYTES) -> tuple[str, bool]:
    """Return display text bounded by UTF-8 byte length and a truncation flag."""

    text = str(value) if value is not None else ""
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return text, False
    return encoded[:limit].decode("utf-8", errors="ignore"), True
