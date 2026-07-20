from __future__ import annotations

from argparse import Namespace
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, cast

import scripts.dev as dev


class _FinishedProcess:
    pid = 999_999

    def poll(self) -> int:
        return 0


def test_dev_runner_builds_portable_proxy_and_origin_commands(
    monkeypatch: Any, tmp_path: Path
) -> None:
    client_directory = tmp_path / "client"
    (client_directory / "node_modules").mkdir(parents=True)
    launches: list[tuple[list[str], dict[str, object]]] = []

    args = Namespace(
        root=str(tmp_path),
        host="0.0.0.0",
        backend_port=19_009,
        frontend_port=19_010,
        no_reload=True,
        open=False,
        compstagram=False,
        compstagram_port=21_000,
        allow_origin=["http://192.168.1.50:19010"],
    )

    def fake_popen(command: list[str], **options: object) -> _FinishedProcess:
        launches.append((command, options))
        return _FinishedProcess()

    monkeypatch.setattr(dev, "CLIENT_DIRECTORY", client_directory)
    monkeypatch.setattr(dev, "parse_args", lambda: args)
    monkeypatch.setattr(dev, "find_command", lambda name: "npm")
    monkeypatch.setattr(dev, "project_python", lambda: Path(sys.executable))
    monkeypatch.setattr(
        dev.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0),
    )
    monkeypatch.setattr(dev.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(dev, "install_shutdown_handlers", lambda event: {})

    assert dev.main() == 0
    assert len(launches) == 2

    backend = launches[0][0]
    assert backend[:3] == [sys.executable, "-m", "trailhead"]
    assert [
        backend[index + 1]
        for index, argument in enumerate(backend)
        if argument == "--allow-origin"
    ] == [
        "http://127.0.0.1:19010",
        "http://192.168.1.50:19010",
    ]

    frontend = launches[1]
    environment = cast(dict[str, str], frontend[1]["env"])
    assert environment["TRAILHEAD_BACKEND_URL"] == "http://127.0.0.1:19009"


class _RacingProcess:
    pid = 999_998

    def poll(self) -> None:
        return None

    def send_signal(self, requested_signal: int) -> None:
        raise ProcessLookupError

    def terminate(self) -> None:
        raise ProcessLookupError


def test_dev_runner_shutdown_ignores_a_concurrent_process_exit(
    monkeypatch: Any,
) -> None:
    if os.name != "nt":
        monkeypatch.setattr(
            dev.os, "killpg", lambda *args: (_ for _ in ()).throw(ProcessLookupError())
        )

    dev.stop_process(cast(Any, _RacingProcess()))
