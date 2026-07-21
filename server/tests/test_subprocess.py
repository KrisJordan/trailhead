from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys
import threading
from typing import cast

from fastapi import WebSocket
import pytest
from starlette.websockets import WebSocketState

from trailhead.async_python_subprocess import AsyncPythonSubprocess


class RecordingSocket:
    def __init__(self) -> None:
        self.client_state = WebSocketState.CONNECTED
        self.messages: list[dict[str, object]] = []

    async def send_text(self, data: str) -> None:
        self.messages.append(json.loads(data))


async def _wait_for_stdout(socket: RecordingSocket, expected: str) -> None:
    async def wait() -> None:
        while True:
            for message in socket.messages:
                if message.get("type") != "STDOUT":
                    continue
                data = cast(dict[str, object], message["data"])
                if expected in cast(str, data["data"]):
                    return
            await asyncio.sleep(0.01)

    await asyncio.wait_for(wait(), timeout=10)


async def _run_failing_module(
    tmp_path: Path, module_name: str, source: str
) -> dict[str, object]:
    (tmp_path / f"{module_name}.py").write_text(source, encoding="utf-8")
    recording_socket = RecordingSocket()
    process = AsyncPythonSubprocess(
        module_name,
        cast(WebSocket, recording_socket),
        project_root=tmp_path,
    )

    await process.start()
    assert await asyncio.wait_for(process.await_end(), timeout=10) == 1

    stderr = [
        message for message in recording_socket.messages if message["type"] == "STDERR"
    ]
    assert len(stderr) == 1
    data = cast(dict[str, object], stderr[0]["data"])
    return cast(dict[str, object], json.loads(cast(str, data["data"])))


def _write_descendant_module(
    module: Path,
    sentinel: Path,
    *,
    keep_parent_alive: bool = True,
    ready_file: Path | None = None,
) -> None:
    child_code = (
        "import time\n"
        "from pathlib import Path\n"
        "time.sleep(0.75)\n"
        f"Path({str(sentinel)!r}).write_text('survived', encoding='utf-8')\n"
    )
    parent_tail = "while True:\n    time.sleep(1)\n" if keep_parent_alive else ""
    ready_line = (
        f"from pathlib import Path\nPath({str(ready_file)!r}).write_text('ready')\n"
        if ready_file is not None
        else ""
    )
    module.write_text(
        "import subprocess\n"
        "import sys\n"
        "import time\n"
        "subprocess.Popen(\n"
        f"    [sys.executable, '-c', {child_code!r}],\n"
        "    stdin=subprocess.DEVNULL,\n"
        "    stdout=subprocess.DEVNULL,\n"
        "    stderr=subprocess.DEVNULL,\n"
        ")\n"
        f"{ready_line}"
        "print('descendant started', flush=True)\n"
        f"{parent_tail}",
        encoding="utf-8",
    )


def test_child_command_uses_current_interpreter(tmp_path: Path) -> None:
    socket = cast(WebSocket, RecordingSocket())
    process = AsyncPythonSubprocess("example", socket, project_root=tmp_path)

    assert process.command == (
        sys.executable,
        "-u",
        "-m",
        "trailhead.wrappers.module",
        "example",
    )


async def test_syntax_error_is_rooted_at_student_module(tmp_path: Path) -> None:
    payload = await _run_failing_module(
        tmp_path,
        "syntax_example",
        "course = 'COMP 110'\nanswer = 1 +\n",
    )

    assert payload["type"] == "SyntaxError"
    frames = cast(list[dict[str, object]], payload["stack_trace"])
    assert [
        (frame["filename"], frame["lineno"], frame["name"]) for frame in frames
    ] == [("syntax_example.py", 2, "<module>")]
    assert frames[0]["line"] == "answer = 1 +\n"


async def test_runtime_error_is_rooted_at_student_module_with_locals(
    tmp_path: Path,
) -> None:
    payload = await _run_failing_module(
        tmp_path,
        "runtime_example",
        "course = 'COMP 110'\n"
        "attempt = 2\n"
        "def divide():\n"
        "    divisor = 0\n"
        "    return attempt / divisor\n"
        "divide()\n",
    )

    assert payload["type"] == "ZeroDivisionError"
    frames = cast(list[dict[str, object]], payload["stack_trace"])
    assert [
        (frame["filename"], frame["lineno"], frame["name"]) for frame in frames
    ] == [
        ("runtime_example.py", 6, "<module>"),
        ("runtime_example.py", 5, "divide"),
    ]
    assert cast(dict[str, object], frames[-1]["locals"])["divisor"] == 0
    assert all(
        "trailhead/wrappers" not in cast(str, frame["filename"]) for frame in frames
    )


async def test_child_runs_without_asyncio_subprocess_transport(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def unsupported_transport(*args: object, **kwargs: object) -> None:
        raise NotImplementedError("selector event loops cannot create subprocesses")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", unsupported_transport)
    (tmp_path / "portable_example.py").write_text(
        'print("Hello, \N{SNOWMAN}!")\n', encoding="utf-8"
    )
    recording_socket = RecordingSocket()
    process = AsyncPythonSubprocess(
        "portable_example",
        cast(WebSocket, recording_socket),
        project_root=tmp_path,
    )

    assert await process.start() > 0
    assert await asyncio.wait_for(process.await_end(), timeout=10) == 0

    stdout = [
        message for message in recording_socket.messages if message["type"] == "STDOUT"
    ]
    assert stdout[0]["data"]["data"] == "Hello, \N{SNOWMAN}!\n"  # type: ignore[index]
    assert recording_socket.messages[-1]["type"] == "EXIT"


@pytest.mark.skipif(os.name == "nt", reason="POSIX process groups are not on Windows")
async def test_child_starts_in_an_isolated_posix_process_group(tmp_path: Path) -> None:
    (tmp_path / "group_example.py").write_text(
        "import time\nprint('ready', flush=True)\ntime.sleep(30)\n",
        encoding="utf-8",
    )
    recording_socket = RecordingSocket()
    process = AsyncPythonSubprocess(
        "group_example",
        cast(WebSocket, recording_socket),
        project_root=tmp_path,
    )
    pid = await process.start()

    try:
        await _wait_for_stdout(recording_socket, "ready")
        get_process_group = getattr(os, "getpgid")
        assert get_process_group(pid) == pid
    finally:
        process.kill()
        await asyncio.wait_for(process.await_end(), timeout=10)


@pytest.mark.parametrize("stop_mode", ["kill", "disconnect"])
async def test_stopping_child_terminates_its_descendants(
    stop_mode: str, tmp_path: Path
) -> None:
    sentinel = tmp_path / f"{stop_mode}-descendant-survived"
    _write_descendant_module(tmp_path / "descendant_example.py", sentinel)
    recording_socket = RecordingSocket()
    process = AsyncPythonSubprocess(
        "descendant_example",
        cast(WebSocket, recording_socket),
        project_root=tmp_path,
    )
    await process.start()

    try:
        await _wait_for_stdout(recording_socket, "descendant started")
        if stop_mode == "kill":
            process.kill()
        else:
            recording_socket.client_state = WebSocketState.DISCONNECTED

        assert await asyncio.wait_for(process.await_end(), timeout=10) != 0
        await asyncio.sleep(1)
        assert not sentinel.exists()
    finally:
        process.kill()


async def test_parent_exit_terminates_its_remaining_descendants(
    tmp_path: Path,
) -> None:
    sentinel = tmp_path / "orphaned-descendant-survived"
    _write_descendant_module(
        tmp_path / "orphan_example.py", sentinel, keep_parent_alive=False
    )
    recording_socket = RecordingSocket()
    process = AsyncPythonSubprocess(
        "orphan_example",
        cast(WebSocket, recording_socket),
        project_root=tmp_path,
    )
    await process.start()

    assert await asyncio.wait_for(process.await_end(), timeout=10) == 0
    await asyncio.sleep(1)
    assert not sentinel.exists()


async def test_cancelling_start_cleans_up_the_started_process_tree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sentinel = tmp_path / "cancelled-descendant-survived"
    ready_file = tmp_path / "cancelled-descendant-ready"
    _write_descendant_module(
        tmp_path / "cancelled_example.py", sentinel, ready_file=ready_file
    )
    process = AsyncPythonSubprocess(
        "cancelled_example",
        cast(WebSocket, RecordingSocket()),
        project_root=tmp_path,
    )
    original_open_process = process._open_process
    open_process_returned = threading.Event()
    release_open_process = threading.Event()

    def delayed_open_process(environment: dict[str, str]) -> tuple[object, object]:
        result = original_open_process(environment)
        open_process_returned.set()
        if not release_open_process.wait(timeout=10):
            raise TimeoutError("test did not release the Popen worker")
        return result

    monkeypatch.setattr(process, "_open_process", delayed_open_process)
    start_task = asyncio.create_task(process.start())

    try:
        assert await asyncio.to_thread(open_process_returned.wait, 10)
        for _ in range(1_000):
            if ready_file.exists():
                break
            await asyncio.sleep(0.01)
        else:
            raise AssertionError("descendant did not start")

        start_task.cancel()
        release_open_process.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(start_task, timeout=10)

        await asyncio.sleep(1)
        assert not sentinel.exists()
    finally:
        release_open_process.set()
        process.kill()


async def test_child_accepts_input_after_unicode_prompt(tmp_path: Path) -> None:
    (tmp_path / "prompt_example.py").write_text(
        'answer = input("caf\N{LATIN SMALL LETTER E WITH ACUTE}? ")\nprint(answer)\n',
        encoding="utf-8",
    )
    recording_socket = RecordingSocket()
    process = AsyncPythonSubprocess(
        "prompt_example",
        cast(WebSocket, recording_socket),
        project_root=tmp_path,
    )
    await process.start()

    for _ in range(200):
        if any(
            message.get("type") == "STDOUT"
            and cast(dict[str, object], message["data"]).get("is_input_prompt")
            for message in recording_socket.messages
        ):
            break
        await asyncio.sleep(0.01)
    else:
        process.kill()
        raise AssertionError("child did not publish its input prompt")

    await process.write("yes")
    assert await asyncio.wait_for(process.await_end(), timeout=10) == 0
    stdout_text = "".join(
        cast(dict[str, str], message["data"])["data"]
        for message in recording_socket.messages
        if message["type"] == "STDOUT"
    )
    assert "caf\N{LATIN SMALL LETTER E WITH ACUTE}? " in stdout_text
    assert "yes\n" in stdout_text
