"""Command-line entry point for the Trailhead server."""

from __future__ import annotations

import argparse
from copy import deepcopy
import logging
from pathlib import Path
import sys
from typing import Any, Sequence, TextIO, TypedDict

import uvicorn
from uvicorn.config import LOGGING_CONFIG

from . import __version__
from .project import set_project_root
from .websocket_origin import (
    ALLOWED_ORIGINS_ENV,
    add_allowed_websocket_origins,
)

PACKAGE_DIR = Path(__file__).resolve().parent


class UvicornOptions(TypedDict, total=False):
    host: str
    port: int
    log_level: str
    access_log: bool
    log_config: dict[str, Any]
    reload: bool
    reload_dirs: list[str]


class TrailheadLogHandler(logging.StreamHandler):
    """Keep Uvicorn diagnostics while hiding routine WebSocket status updates."""

    def __init__(
        self,
        browser_url: str,
        suppress_websocket_status_logs: bool,
        announce_after_application_startup: bool = False,
        stream: TextIO | None = None,
    ) -> None:
        super().__init__(stream)
        self.browser_url = browser_url
        self.suppress_websocket_status_logs = suppress_websocket_status_logs
        self.announce_after_application_startup = announce_after_application_startup

    @staticmethod
    def _is_websocket_status(record: logging.LogRecord) -> bool:
        if record.name != "uvicorn.error" or record.levelno != logging.INFO:
            return False
        template = str(record.msg)
        return template.startswith('%s - "WebSocket %s"') or record.getMessage() in {
            "connection open",
            "connection closed",
        }

    @staticmethod
    def _is_server_started(record: logging.LogRecord) -> bool:
        return (
            record.name == "uvicorn.error"
            and record.levelno == logging.INFO
            and str(record.msg).startswith("Uvicorn running on ")
        )

    @staticmethod
    def _is_application_started(record: logging.LogRecord) -> bool:
        return (
            record.name == "uvicorn.error"
            and record.levelno == logging.INFO
            and record.getMessage() == "Application startup complete."
        )

    def emit(self, record: logging.LogRecord) -> None:
        if self.suppress_websocket_status_logs and self._is_websocket_status(record):
            return

        super().emit(record)
        if (
            self.announce_after_application_startup
            and self._is_application_started(record)
        ) or (
            not self.announce_after_application_startup
            and self._is_server_started(record)
        ):
            announcement = logging.LogRecord(
                name="uvicorn.error",
                level=logging.INFO,
                pathname=__file__,
                lineno=0,
                msg=f"Open Trailhead in your browser at {self.browser_url}",
                args=(),
                exc_info=None,
            )
            super().emit(announcement)


def _port(value: str) -> int:
    port = int(value)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def _url_host(host: str) -> str:
    """Format a bind host for display in an HTTP URL."""

    if ":" in host and not host.startswith("["):
        return f"[{host}]"
    return host


def _uvicorn_log_config(
    browser_url: str,
    *,
    suppress_websocket_status_logs: bool,
    announce_after_application_startup: bool,
) -> dict[str, Any]:
    """Return Uvicorn's logging config with Trailhead's console behavior."""

    config = deepcopy(LOGGING_CONFIG)
    default_handler = config["handlers"]["default"]
    default_handler.pop("class")
    default_handler.update(
        {
            "()": "trailhead.__main__.TrailheadLogHandler",
            "browser_url": browser_url,
            "suppress_websocket_status_logs": suppress_websocket_status_logs,
            "announce_after_application_startup": announce_after_application_startup,
        }
    )
    return config


def build_parser() -> argparse.ArgumentParser:
    """Build Trailhead's command-line argument parser."""

    parser = argparse.ArgumentParser(description="Run the Trailhead server")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="interface to bind (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=_port,
        default=1110,
        help="TCP port to bind (default: 1110)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help=(
            "project containing the Python modules to serve "
            "(default: current directory)"
        ),
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="restart when Trailhead server source files change",
    )
    parser.add_argument(
        "--log-level",
        choices=("critical", "error", "warning", "info", "debug", "trace"),
        default="info",
        help="Uvicorn log level (default: info)",
    )
    parser.add_argument(
        "--allow-origin",
        action="append",
        default=[],
        metavar="ORIGIN",
        help=(
            "allow an exact browser WebSocket origin (repeatable; additional "
            f"origins may be set with {ALLOWED_ORIGINS_ENV})"
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run Trailhead using an installable, host-independent configuration."""

    args = build_parser().parse_args(argv)
    try:
        project_root = set_project_root(args.root)
        add_allowed_websocket_origins(args.allow_origin)
    except (OSError, ValueError) as error:
        print(f"trailhead: {error}", file=sys.stderr)
        return 2

    browser_url = f"http://{_url_host(args.host)}:{args.port}"
    debug_logging = args.log_level in {"debug", "trace"}

    print(f"Serving project {project_root}", flush=True)
    print(f"Starting Trailhead server at {browser_url}", flush=True)
    print("Press Ctrl+C to stop the Trailhead server", flush=True)

    options: UvicornOptions = {
        "host": args.host,
        "port": args.port,
        "log_level": args.log_level,
        "access_log": debug_logging,
        "log_config": _uvicorn_log_config(
            browser_url,
            suppress_websocket_status_logs=not debug_logging,
            announce_after_application_startup=args.reload,
        ),
    }
    if args.reload:
        options.update(
            reload=True,
            reload_dirs=[str(PACKAGE_DIR)],
        )

    # An import string works both normally and in Uvicorn's spawned reload
    # worker. Any startup/import failure remains visible to the caller.
    uvicorn.run("trailhead.app:app", **options)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
