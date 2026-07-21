#!/usr/bin/env python3
"""Create a host-native Trailhead development environment.

This script intentionally uses only the Python standard library and uv so it works
before Trailhead's dependencies are installed. It is safe to run more than once.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SERVER_DIRECTORY = REPOSITORY_ROOT / "server"
CLIENT_DIRECTORY = REPOSITORY_ROOT / "client"
MINIMUM_PYTHON = (3, 11)
MINIMUM_NODE = (22, 12, 0)
PINNED_PYTHON = (REPOSITORY_ROOT / ".python-version").read_text().strip()


def find_command(name: str) -> str | None:
    """Find an executable, including Windows' command shim suffixes."""
    candidates = [name]
    if os.name == "nt":
        candidates = [f"{name}.cmd", f"{name}.exe", name]
    for candidate in candidates:
        executable = shutil.which(candidate)
        if executable:
            return executable
    return None


def run(command: list[str], *, cwd: Path = REPOSITORY_ROOT) -> None:
    """Run a setup command and stop immediately if it fails."""
    display = subprocess.list2cmdline(command)
    print(f"\n> {display}", flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def check_python() -> None:
    if sys.version_info < MINIMUM_PYTHON:
        required = ".".join(str(part) for part in MINIMUM_PYTHON)
        current = f"{sys.version_info.major}.{sys.version_info.minor}"
        raise SystemExit(
            f"Trailhead requires Python {required} or newer; this is Python {current}. "
            "Install a newer Python and run this script with that interpreter."
        )


def check_node() -> tuple[str, str]:
    node = find_command("node")
    npm = find_command("npm")
    if not node or not npm:
        raise SystemExit(
            "Node.js and npm were not found. Install Node.js 22.12 or newer, open a "
            "new terminal, and run this script again."
        )

    version = subprocess.run(
        [node, "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    match = re.fullmatch(r"v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-+].*)?", version)
    parsed = tuple(int(part or 0) for part in match.groups()) if match else ()
    if parsed < MINIMUM_NODE:
        required = ".".join(str(part) for part in MINIMUM_NODE)
        raise SystemExit(
            f"Trailhead requires Node.js {required} or newer; found "
            f"{version or 'an unknown version'}."
        )
    return node, npm


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Set up Trailhead directly on macOS, Windows, or Linux."
    )
    parser.add_argument(
        "--skip-client",
        action="store_true",
        help="Install only Python dependencies; do not install or build the web client.",
    )
    parser.add_argument(
        "--runtime-only",
        action="store_true",
        help="Skip Python test, formatting, and type-checking dependencies.",
    )
    parser.add_argument(
        "--student",
        action="store_true",
        help="Install the optional notebook, plotting, data, and image packages.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    check_python()

    uv = find_command("uv")
    if not uv:
        raise SystemExit(
            "uv was not found. Install uv from https://docs.astral.sh/uv/ and "
            "run this script again."
        )

    npm: str | None = None
    if not args.skip_client:
        _, npm = check_node()

    sync_command = [
        uv,
        "sync",
        "--project",
        str(SERVER_DIRECTORY),
        "--locked",
        "--python",
        PINNED_PYTHON,
    ]
    if args.runtime_only:
        sync_command.append("--no-dev")
    if args.student:
        sync_command.extend(["--extra", "student"])
    run(sync_command)

    if npm:
        run([npm, "ci"], cwd=CLIENT_DIRECTORY)
        run([npm, "run", "build"], cwd=CLIENT_DIRECTORY)

    if args.skip_client:
        print("\nTrailhead's Python backend is installed.")
        print(
            "The browser client was intentionally skipped, so the web interface "
            "is not ready. Rerun this script without --skip-client to build it."
        )
        print(
            "Backend-only command:\n\n  uv run --project server trailhead --root demo\n"
        )
    else:
        print("\nTrailhead is ready.")
        print(
            "Start the development servers with:\n\n"
            "  uv run --project server python scripts/dev.py\n"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.returncode) from error
