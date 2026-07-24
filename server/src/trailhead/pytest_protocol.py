"""Shared constants and normalization helpers for the pytest child protocol."""

from __future__ import annotations

EVENT_PREFIX = "TRAILHEAD_PYTEST_EVENT:"
"""Prefix that distinguishes child protocol records from ordinary pytest output."""

MAX_OUTPUT_BYTES = 64 * 1024
"""Maximum encoded size of any user-controlled text field sent to the browser."""


def limited_text(value: object, limit: int = MAX_OUTPUT_BYTES) -> tuple[str, bool]:
    """Return display text bounded by UTF-8 byte length and a truncation flag."""

    text = str(value) if value is not None else ""
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return text, False
    return encoded[:limit].decode("utf-8", errors="ignore"), True
