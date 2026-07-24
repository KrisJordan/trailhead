#!/usr/bin/env python3
"""Run Trailhead's backend and web client without Docker or Caddy."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time
from types import FrameType
from typing import Callable, TypedDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CLIENT_DIRECTORY = REPOSITORY_ROOT / "client"
COMPSTAGRAM_DIRECTORY = REPOSITORY_ROOT / "compstagram"
VENV_DIRECTORY = REPOSITORY_ROOT / "server" / ".venv"

SignalHandler = Callable[[int, FrameType | None], object] | int | signal.Handlers | None


class ProcessOptions(TypedDict, total=False):
    creationflags: int
    start_new_session: bool


def find_command(name: str) -> str | None:
    candidates = [name]
    if sys.platform == "win32":
        candidates = [f"{name}.cmd", f"{name}.exe", name]
    for candidate in candidates:
        executable = shutil.which(candidate)
        if executable:
            return executable
    return None


def project_python() -> Path:
    if sys.platform == "win32":
        candidate = VENV_DIRECTORY / "Scripts" / "python.exe"
    else:
        candidate = VENV_DIRECTORY / "bin" / "python"
    return candidate if candidate.is_file() else Path(sys.executable)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Trailhead's native development servers."
    )
    parser.add_argument(
        "root",
        nargs="?",
        default="demo",
        help="Directory containing the Python project to inspect (default: demo).",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--backend-port", type=int, default=1109)
    parser.add_argument("--frontend-port", type=int, default=1110)
    parser.add_argument(
        "--no-reload", action="store_true", help="Disable backend auto-reload."
    )
    parser.add_argument(
        "--open", action="store_true", help="Open Trailhead in the default browser."
    )
    parser.add_argument(
        "--compstagram",
        action="store_true",
        help="Also serve the optional local Compstagram template.",
    )
    parser.add_argument(
        "--compstagram-port",
        type=int,
        default=2100,
        help="Compstagram template port (default: 2100).",
    )
    parser.add_argument(
        "--allow-origin",
        action="append",
        default=[],
        metavar="ORIGIN",
        help=(
            "allow an additional exact browser WebSocket origin (repeatable; "
            "needed for LAN access when --host is a wildcard)"
        ),
    )
    return parser.parse_args()


def process_options() -> ProcessOptions:
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def url_host(host: str, *, connect_to_wildcard: bool = False) -> str:
    """Return a host suitable for a URL, including IPv6 brackets."""
    if connect_to_wildcard:
        if host == "0.0.0.0":
            host = "127.0.0.1"
        elif host == "::":
            host = "::1"
    if ":" in host and not host.startswith("["):
        return f"[{host}]"
    return host


def stop_process(process: subprocess.Popen[bytes]) -> None:
    """Gracefully stop a process and the children it launched."""
    if process.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(process.pid, signal.SIGTERM)
    except (OSError, ValueError):
        try:
            process.terminate()
        except OSError:
            # The process may have exited between poll() and terminate().
            pass


def force_stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except (OSError, ValueError):
        try:
            process.kill()
        except OSError:
            # A concurrent natural exit is already the desired result.
            pass


def stop_all(processes: list[subprocess.Popen[bytes]]) -> None:
    for process in processes:
        stop_process(process)

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and any(
        process.poll() is None for process in processes
    ):
        time.sleep(0.05)

    for process in processes:
        force_stop_process(process)


def install_shutdown_handlers(
    shutdown_requested: threading.Event,
) -> dict[signal.Signals, SignalHandler]:
    """Turn service-manager termination signals into orderly unwinding."""

    previous: dict[signal.Signals, SignalHandler] = {}

    def request_shutdown(signum: int, frame: object) -> None:
        shutdown_requested.set()

    names = ["SIGTERM", "SIGHUP"]
    if sys.platform == "win32":
        names.append("SIGBREAK")
    for name in names:
        shutdown_signal = getattr(signal, name, None)
        if shutdown_signal is None:
            continue
        previous[shutdown_signal] = signal.getsignal(shutdown_signal)
        signal.signal(shutdown_signal, request_shutdown)
    return previous


def restore_signal_handlers(previous: dict[signal.Signals, SignalHandler]) -> None:
    for shutdown_signal, handler in previous.items():
        signal.signal(shutdown_signal, handler)


def main() -> int:
    args = parse_args()
    host: str = args.host
    backend_port: int = args.backend_port
    frontend_port: int = args.frontend_port
    root = Path(args.root)
    if not root.is_absolute():
        root = (REPOSITORY_ROOT / root).resolve()
    if not root.is_dir():
        raise SystemExit(f"Project root does not exist or is not a directory: {root}")

    npm = find_command("npm")
    if not npm:
        raise SystemExit(
            "npm was not found. Install Node.js 22.12 or newer and run "
            "scripts/bootstrap.py first."
        )
    if not (CLIENT_DIRECTORY / "node_modules").is_dir():
        raise SystemExit(
            "Client dependencies are not installed. Run scripts/bootstrap.py first."
        )
    if (
        args.compstagram
        and not (COMPSTAGRAM_DIRECTORY / "dist" / "bundle.js").is_file()
    ):
        raise SystemExit(
            "The Compstagram template has not been built. Run `npm ci --prefix "
            "compstagram` and `npm run build --prefix compstagram` first."
        )

    python = project_python()
    import_check = subprocess.run(
        [str(python), "-c", "import trailhead"],
        cwd=REPOSITORY_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if import_check.returncode:
        raise SystemExit(
            f"Trailhead is not installed for {python}. Run scripts/bootstrap.py first."
        )

    backend_command: list[str] = [
        str(python),
        "-m",
        "trailhead",
        "--host",
        host,
        "--port",
        str(backend_port),
        "--root",
        str(root),
    ]
    if not args.no_reload:
        backend_command.append("--reload")

    # Pass the browser-visible URL explicitly. Loopback same-origin traffic is
    # trusted automatically; concrete LAN hostnames still require an exact
    # allowlist entry because Trailhead intentionally distrusts remote origins.
    visible_host = url_host(host, connect_to_wildcard=True)
    browser_origin = f"http://{visible_host}:{frontend_port}"
    for origin in [browser_origin, *args.allow_origin]:
        backend_command.extend(["--allow-origin", origin])

    frontend_command: list[str] = [
        npm,
        "run",
        "dev",
        "--",
        "--host",
        host,
        "--port",
        str(frontend_port),
        "--strictPort",
    ]
    if args.open:
        frontend_command.append("--open")

    proxy_host = visible_host
    frontend_environment = os.environ.copy()
    frontend_environment["TRAILHEAD_BACKEND_URL"] = (
        f"http://{proxy_host}:{backend_port}"
    )

    print(
        f"Starting Trailhead at "
        f"http://{visible_host}:"
        f"{frontend_port}\n"
        f"Watching Python files in {root}\n"
        "Press Ctrl+C to stop all servers.\n",
        flush=True,
    )
    if args.compstagram:
        print(
            f"Serving Compstagram at http://{visible_host}:{args.compstagram_port}\n",
            flush=True,
        )

    options = process_options()
    processes: list[subprocess.Popen[bytes]] = []
    exit_code = 0
    shutdown_requested = threading.Event()
    previous_signal_handlers = install_shutdown_handlers(shutdown_requested)
    try:
        processes.append(
            subprocess.Popen(
                backend_command,
                cwd=REPOSITORY_ROOT,
                **options,
            )
        )
        if args.compstagram:
            processes.append(
                subprocess.Popen(
                    [
                        str(python),
                        "-m",
                        "http.server",
                        str(args.compstagram_port),
                        "--bind",
                        host,
                        "--directory",
                        str(COMPSTAGRAM_DIRECTORY),
                    ],
                    cwd=REPOSITORY_ROOT,
                    **options,
                )
            )
        processes.append(
            subprocess.Popen(
                frontend_command,
                cwd=CLIENT_DIRECTORY,
                env=frontend_environment,
                **options,
            )
        )
        while not shutdown_requested.is_set():
            for process in processes:
                return_code = process.poll()
                if return_code is not None:
                    exit_code = return_code
                    return exit_code
            time.sleep(0.1)
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        print("\nStopping Trailhead...", flush=True)
        try:
            stop_all(processes)
        finally:
            restore_signal_handlers(previous_signal_handlers)


if __name__ == "__main__":
    raise SystemExit(main())
