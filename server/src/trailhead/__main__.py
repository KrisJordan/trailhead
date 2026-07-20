"""Command-line entry point for the Trailhead server."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

import uvicorn

from . import __version__
from .project import set_project_root
from .websocket_origin import (
    ALLOWED_ORIGINS_ENV,
    add_allowed_websocket_origins,
)

PACKAGE_DIR = Path(__file__).resolve().parent


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
        help="project containing the Python modules to serve (default: current directory)",
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

    print(f"Serving project {project_root}")
    print(f"Starting Trailhead server at http://{_url_host(args.host)}:{args.port}")
    print("Press Ctrl+C to stop the Trailhead server")

    options: dict[str, object] = {
        "host": args.host,
        "port": args.port,
        "log_level": args.log_level,
    }
    if args.reload:
        options.update(
            reload=True,
            reload_dirs=[str(PACKAGE_DIR)],
        )

    # An import string works both normally and in Uvicorn's spawned reload
    # worker. Any startup/import failure remains visible to the caller.
    uvicorn.run("trailhead.app:app", **options)  # type: ignore[arg-type]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
