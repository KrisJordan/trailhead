from __future__ import annotations

from io import StringIO
import logging
import os
from pathlib import Path
from typing import Any

from trailhead.__main__ import PACKAGE_DIR, TrailheadLogHandler, main
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
    log_config = call.pop("log_config")
    assert call == {
        "app": "trailhead.app:app",
        "host": "0.0.0.0",
        "port": 8765,
        "log_level": "debug",
        "access_log": True,
    }
    default_handler = log_config["handlers"]["default"]
    assert default_handler["browser_url"] == "http://0.0.0.0:8765"
    assert default_handler["suppress_websocket_status_logs"] is False
    assert default_handler["announce_after_application_startup"] is False
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
    default_handler = call["log_config"]["handlers"]["default"]
    assert default_handler["browser_url"] == "http://127.0.0.1:1110"
    assert default_handler["suppress_websocket_status_logs"] is True
    assert default_handler["announce_after_application_startup"] is True
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


def _log_record(
    message: str,
    *args: object,
    level: int = logging.INFO,
) -> logging.LogRecord:
    return logging.LogRecord(
        name="uvicorn.error",
        level=level,
        pathname=__file__,
        lineno=0,
        msg=message,
        args=args,
        exc_info=None,
    )


def test_regular_logging_ends_startup_with_browser_url_and_hides_websockets() -> None:
    stream = StringIO()
    handler = TrailheadLogHandler(
        "http://127.0.0.1:1110",
        suppress_websocket_status_logs=True,
        stream=stream,
    )
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    handler.emit(
        _log_record(
            "Uvicorn running on %s://%s:%d (Press CTRL+C to quit)",
            "http",
            "127.0.0.1",
            1110,
        )
    )
    handler.emit(
        _log_record(
            '%s - "WebSocket %s" [accepted]',
            "127.0.0.1:60399",
            "/ws",
        )
    )
    handler.emit(_log_record("connection open"))
    handler.emit(_log_record("A warning remains visible", level=logging.WARNING))

    assert stream.getvalue().splitlines() == [
        "INFO: Uvicorn running on http://127.0.0.1:1110 (Press CTRL+C to quit)",
        "INFO: Open Trailhead in your browser at http://127.0.0.1:1110",
        "WARNING: A warning remains visible",
    ]


def test_debug_logging_keeps_websocket_status_updates() -> None:
    stream = StringIO()
    handler = TrailheadLogHandler(
        "http://127.0.0.1:1110",
        suppress_websocket_status_logs=False,
        stream=stream,
    )
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    handler.emit(
        _log_record(
            '%s - "WebSocket %s" [accepted]',
            "127.0.0.1:60399",
            "/ws",
        )
    )
    handler.emit(_log_record("connection open"))

    assert stream.getvalue().splitlines() == [
        'INFO: 127.0.0.1:60399 - "WebSocket /ws" [accepted]',
        "INFO: connection open",
    ]


def test_reload_logging_announces_browser_url_after_application_startup() -> None:
    stream = StringIO()
    handler = TrailheadLogHandler(
        "http://127.0.0.1:1110",
        suppress_websocket_status_logs=True,
        announce_after_application_startup=True,
        stream=stream,
    )
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    handler.emit(
        _log_record(
            "Uvicorn running on %s://%s:%d (Press CTRL+C to quit)",
            "http",
            "127.0.0.1",
            1110,
        )
    )
    handler.emit(_log_record("Application startup complete."))

    assert stream.getvalue().splitlines() == [
        "INFO: Uvicorn running on http://127.0.0.1:1110 (Press CTRL+C to quit)",
        "INFO: Application startup complete.",
        "INFO: Open Trailhead in your browser at http://127.0.0.1:1110",
    ]
