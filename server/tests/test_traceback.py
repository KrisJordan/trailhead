from __future__ import annotations

from pathlib import Path

from trailhead.wrappers._traceback import display_filename, exception_payload


def test_display_filename_uses_posix_project_relative_path(tmp_path: Path) -> None:
    source = tmp_path / "package" / "example.py"
    assert display_filename(str(source), tmp_path) == "package/example.py"


def test_exception_payload_has_no_container_paths() -> None:
    try:
        raise ValueError("portable")
    except ValueError as error:
        payload = exception_payload(error)

    assert payload["type"] == "ValueError"
    assert payload["message"] == "portable"
    assert "/workspace/" not in str(payload)
