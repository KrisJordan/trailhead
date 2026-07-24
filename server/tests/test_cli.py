from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from trailhead.__main__ import PACKAGE_DIR, main
from trailhead.project import PROJECT_ROOT_ENV
from trailhead.websocket_origin import ALLOWED_ORIGINS_ENV


def test_cli_passes_native_options_to_uvicorn(monkeypatch: Any, tmp_path: Path) -> None:
    call: dict[str, Any] = {}

    def fake_run(app: str, **options: object) -> None:
        call["app"] = app
        call.update(options)

    monkeypatch.setattr("trailhead.__main__.uvicorn.run", fake_run)

    result = main(
        [
            "--root",
            str(tmp_path),
            "--host",
            "0.0.0.0",
            "--port",
            "8765",
            "--log-level",
            "debug",
        ]
    )

    assert result == 0
    assert call == {
        "app": "trailhead.app:app",
        "host": "0.0.0.0",
        "port": 8765,
        "log_level": "debug",
        "access_log": True,
    }
    assert os.environ[PROJECT_ROOT_ENV] == str(tmp_path.resolve())


def test_cli_reload_watches_server_source(monkeypatch: Any, tmp_path: Path) -> None:
    call: dict[str, Any] = {}

    def fake_run(app: str, **options: object) -> None:
        call["app"] = app
        call.update(options)

    monkeypatch.setattr("trailhead.__main__.uvicorn.run", fake_run)

    assert main(["--root", str(tmp_path), "--reload"]) == 0
    assert call["port"] == 1110
    assert call["access_log"] is False
    assert call["reload"] is True
    assert call["reload_dirs"] == [str(PACKAGE_DIR)]


def test_cli_reports_invalid_root(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "trailhead.__main__.uvicorn.run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    assert main(["--root", str(tmp_path / "missing")]) == 2


def test_cli_exports_exact_allowed_origins_for_reload_workers(
    monkeypatch: Any, tmp_path: Path
) -> None:
    call: dict[str, Any] = {}
    monkeypatch.delenv(ALLOWED_ORIGINS_ENV, raising=False)
    monkeypatch.setattr(
        "trailhead.__main__.uvicorn.run",
        lambda app, **options: call.update(app=app, **options),
    )

    assert (
        main(
            [
                "--root",
                str(tmp_path),
                "--reload",
                "--allow-origin",
                "HTTPS://Classroom.Example:443/",
                "--allow-origin",
                "http://192.168.1.25:1110",
            ]
        )
        == 0
    )

    assert os.environ[ALLOWED_ORIGINS_ENV] == (
        "http://192.168.1.25:1110,https://classroom.example"
    )
    assert call["reload"] is True


def test_cli_rejects_wildcard_origin(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.delenv(ALLOWED_ORIGINS_ENV, raising=False)
    monkeypatch.setattr(
        "trailhead.__main__.uvicorn.run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not run")),
    )

    assert main(["--root", str(tmp_path), "--allow-origin", "*"]) == 2


def test_cli_displays_a_valid_ipv6_url(
    monkeypatch: Any, tmp_path: Path, capsys: Any
) -> None:
    monkeypatch.setattr("trailhead.__main__.uvicorn.run", lambda *args, **kwargs: None)

    assert main(["--root", str(tmp_path), "--host", "::1"]) == 0

    assert "http://[::1]:1110" in capsys.readouterr().out
