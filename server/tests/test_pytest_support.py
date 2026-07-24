from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Literal, cast

from fastapi import WebSocket
import pytest
from starlette.websockets import WebSocketDisconnect, WebSocketState

from trailhead.project import set_project_root
from trailhead.pytest_plugin import MAX_COLLECTION_BYTES, TrailheadPytestPlugin
from trailhead.pytest_protocol import (
    EVENT_PREFIX,
    MAX_METADATA_BYTES,
    MAX_NODE_ID_BYTES,
)
from trailhead.pytest_subprocess import AsyncPytestSubprocess
from trailhead.pytest_websocket import pytest_websocket


class RecordingSocket:
    def __init__(self) -> None:
        self.client_state = WebSocketState.CONNECTED
        self.messages: list[dict[str, Any]] = []

    async def send_text(self, data: str) -> None:
        self.messages.append(json.loads(data))


class InteractiveSocket(RecordingSocket):
    def __init__(self) -> None:
        super().__init__()
        self._incoming: asyncio.Queue[str | None] = asyncio.Queue()

    async def accept(self) -> None:
        self.client_state = WebSocketState.CONNECTED

    async def receive_text(self) -> str:
        value = await self._incoming.get()
        if value is None:
            self.client_state = WebSocketState.DISCONNECTED
            raise WebSocketDisconnect()
        return value

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        del code, reason
        self.client_state = WebSocketState.DISCONNECTED

    async def command(self, event_type: str, run_id: str, **data: object) -> None:
        await self._incoming.put(
            json.dumps({"type": event_type, "data": {"run_id": run_id, **data}})
        )

    async def disconnect(self) -> None:
        await self._incoming.put(None)


async def _run_pytest(
    tmp_path: Path,
    module: str,
    mode: str,
    node_ids: tuple[str, ...] = (),
    run_id: str = "run-1",
) -> tuple[int, RecordingSocket]:
    socket = RecordingSocket()
    process = AsyncPytestSubprocess(
        module,
        cast(WebSocket, socket),
        run_id,
        mode,
        node_ids,
        tmp_path,
    )
    pid = await process.start()
    await process.send_started(pid)
    return_code = await asyncio.wait_for(process.await_end(), timeout=20)
    return return_code, socket


def _events(socket: RecordingSocket, event_type: str) -> list[dict[str, Any]]:
    return [
        cast(dict[str, Any], message["data"])
        for message in socket.messages
        if message["type"] == event_type
    ]


class _Marker:
    def __init__(self, name: str) -> None:
        self.name = name


class _Item:
    def __init__(
        self,
        node_id: str,
        *,
        name: str = "test_value",
        path: str = "test_bounds.py",
        markers: tuple[str, ...] = (),
    ) -> None:
        self.nodeid = node_id
        self.name = name
        self.location = (path, 0, name)
        self._markers = [_Marker(marker) for marker in markers]

    def iter_markers(self) -> list[_Marker]:
        return self._markers


class _Session:
    def __init__(self, items: list[_Item]) -> None:
        self.items = items


def _test_report(
    node_id: str,
    *,
    path: str = "test_bounds.py",
    outcome: Literal["passed", "failed"] = "passed",
) -> pytest.TestReport:
    return pytest.TestReport(
        nodeid=node_id,
        location=(path, 0, node_id.rsplit("::", 1)[-1]),
        keywords={},
        outcome=outcome,
        longrepr=None if outcome == "passed" else "assert False",
        when="call",
        sections=(),
        duration=0.01,
        start=0,
        stop=0.01,
        user_properties=(),
    )


async def _wait_for_event(
    socket: RecordingSocket, event_type: str, run_id: str
) -> dict[str, Any]:
    async def wait() -> dict[str, Any]:
        while True:
            for message in socket.messages:
                data = cast(dict[str, Any], message["data"])
                if message["type"] == event_type and data.get("run_id") == run_id:
                    return data
            await asyncio.sleep(0.01)

    return await asyncio.wait_for(wait(), timeout=20)


async def test_pytest_collection_preserves_parametrized_node_ids_and_marks(
    tmp_path: Path,
) -> None:
    (tmp_path / "test_parameters.py").write_text(
        "import pytest\n"
        "\n"
        "@pytest.mark.parametrize('value', [1, 2])\n"
        "@pytest.mark.slow\n"
        "def test_value(value):\n"
        "    assert value\n",
        encoding="utf-8",
    )

    return_code, socket = await _run_pytest(tmp_path, "test_parameters", "collect")

    assert return_code == int(pytest.ExitCode.OK)
    assert [message["type"] for message in socket.messages] == [
        "TEST_RUN_STARTED",
        "TESTS_COLLECTED",
        "TEST_RUN_FINISHED",
    ]
    collected = _events(socket, "TESTS_COLLECTED")[0]["tests"]
    assert [test["node_id"] for test in collected] == [
        "test_parameters.py::test_value[1]",
        "test_parameters.py::test_value[2]",
    ]
    assert [test["name"] for test in collected] == ["test_value[1]", "test_value[2]"]
    assert collected[0]["path"] == "test_parameters.py"
    assert collected[0]["line"] == 3
    assert collected[0]["markers"] == ["parametrize", "slow"]
    finished = _events(socket, "TEST_RUN_FINISHED")[0]
    assert finished["status"] == "collected"
    assert finished["summary"]["total"] == 2
    assert all(message["data"]["run_id"] == "run-1" for message in socket.messages)


async def test_result_ids_extend_a_truncated_run_all_collection(
    tmp_path: Path,
) -> None:
    socket = RecordingSocket()
    process = AsyncPytestSubprocess(
        "test_example",
        cast(WebSocket, socket),
        "run-1",
        "run",
        project_root=tmp_path,
    )
    await process.send_started(123)
    visible_node_id = "test_example.py::test_visible"
    omitted_node_id = "test_example.py::test_omitted"
    await process._handle_stdout(
        EVENT_PREFIX
        + json.dumps(
            {
                "type": "TESTS_COLLECTED",
                "data": {
                    "tests": [{"node_id": visible_node_id}],
                    "truncated": True,
                },
            }
        )
        + "\n",
        False,
        cast(Any, object()),
    )
    await process._handle_stdout(
        "pytest progress "
        + EVENT_PREFIX
        + json.dumps(
            {
                "type": "TEST_RESULT",
                "data": {
                    "test": {
                        "node_id": omitted_node_id,
                        "outcome": "failed",
                    }
                },
            }
        )
        + "\n",
        False,
        cast(Any, object()),
    )

    assert process.collected_node_ids == {
        visible_node_id,
        omitted_node_id,
    }
    assert _events(socket, "TEST_RESULT")[0]["test"]["node_id"] == omitted_node_id


async def test_pytest_results_include_all_outcomes_phases_and_captured_output(
    tmp_path: Path,
) -> None:
    (tmp_path / "test_outcomes.py").write_text(
        "import sys\n"
        "import pytest\n"
        "\n"
        "@pytest.fixture\n"
        "def broken_setup():\n"
        "    raise RuntimeError('setup exploded')\n"
        "\n"
        "@pytest.fixture\n"
        "def broken_teardown():\n"
        "    yield\n"
        "    raise RuntimeError('teardown exploded')\n"
        "\n"
        "def test_passes():\n"
        "    print('captured hello')\n"
        "    assert True\n"
        "\n"
        "def test_fails():\n"
        "    print('failure stdout')\n"
        "    print('failure stderr', file=sys.stderr)\n"
        "    assert 1 == 2\n"
        "\n"
        "@pytest.mark.skip(reason='not today')\n"
        "def test_skips():\n"
        "    pass\n"
        "\n"
        "@pytest.mark.xfail(reason='known bug')\n"
        "def test_xfails():\n"
        "    assert False\n"
        "\n"
        "@pytest.mark.xfail(reason='fixed bug')\n"
        "def test_xpasses():\n"
        "    assert True\n"
        "\n"
        "def test_setup_error(broken_setup):\n"
        "    pass\n"
        "\n"
        "def test_teardown_error(broken_teardown):\n"
        "    assert True\n",
        encoding="utf-8",
    )

    return_code, socket = await _run_pytest(tmp_path, "test_outcomes", "run")

    assert return_code == int(pytest.ExitCode.TESTS_FAILED)
    assert len(_events(socket, "TESTS_COLLECTED")[0]["tests"]) == 7
    results = {
        event["test"]["name"]: event["test"] for event in _events(socket, "TEST_RESULT")
    }
    assert {name: result["outcome"] for name, result in results.items()} == {
        "test_passes": "passed",
        "test_fails": "failed",
        "test_skips": "skipped",
        "test_xfails": "xfailed",
        "test_xpasses": "xpassed",
        "test_setup_error": "error",
        "test_teardown_error": "error",
    }

    passing_call = next(
        phase for phase in results["test_passes"]["phases"] if phase["phase"] == "call"
    )
    assert passing_call["stdout"] == f"captured hello{os.linesep}"
    failing_call = next(
        phase for phase in results["test_fails"]["phases"] if phase["phase"] == "call"
    )
    assert failing_call["outcome"] == "failed"
    assert "assert 1 == 2" in failing_call["longrepr"]
    assert "failure stdout" in failing_call["stdout"]
    assert "failure stderr" in failing_call["stderr"]
    assert failing_call["path"].endswith("test_outcomes.py")

    setup_failure = next(
        phase
        for phase in results["test_setup_error"]["phases"]
        if phase["phase"] == "setup"
    )
    teardown_failure = next(
        phase
        for phase in results["test_teardown_error"]["phases"]
        if phase["phase"] == "teardown"
    )
    assert "setup exploded" in setup_failure["message"]
    assert "teardown exploded" in teardown_failure["message"]

    finished = _events(socket, "TEST_RUN_FINISHED")[0]
    assert finished["status"] == "failed"
    assert finished["summary"] == {
        "total": 7,
        "passed": 1,
        "failed": 1,
        "skipped": 1,
        "xfailed": 1,
        "xpassed": 1,
        "error": 2,
    }


async def test_pytest_output_is_bounded_and_marked_truncated(tmp_path: Path) -> None:
    (tmp_path / "test_output.py").write_text(
        "def test_large_output():\n    print('x' * 70000)\n    assert False\n",
        encoding="utf-8",
    )

    _, socket = await _run_pytest(tmp_path, "test_output", "run")

    result = _events(socket, "TEST_RESULT")[0]["test"]
    call = next(phase for phase in result["phases"] if phase["phase"] == "call")
    assert len(call["stdout"].encode("utf-8")) <= 64 * 1024
    assert "stdout" in call["truncated"]


async def test_oversized_parametrized_node_id_is_omitted_safely(
    tmp_path: Path,
) -> None:
    (tmp_path / "test_large_id.py").write_text(
        "import pytest\n"
        "\n"
        "@pytest.mark.parametrize('value', [1], ids=['x' * 20000])\n"
        "def test_large_id(value):\n"
        "    assert value == 2\n",
        encoding="utf-8",
    )

    return_code, socket = await _run_pytest(tmp_path, "test_large_id", "run")

    assert return_code == int(pytest.ExitCode.TESTS_FAILED)
    collection = _events(socket, "TESTS_COLLECTED")[0]
    assert collection == {"tests": [], "total": 1, "truncated": True, "run_id": "run-1"}
    assert not _events(socket, "TEST_RESULT")
    errors = _events(socket, "TEST_ERROR")
    assert len(errors) == 1
    assert "result will be omitted" in errors[0]["message"]
    assert len(json.dumps(errors[0]).encode("utf-8")) < 1024
    finished = _events(socket, "TEST_RUN_FINISHED")[0]
    assert finished["status"] == "failed"
    assert finished["summary"]["failed"] == 1


def test_safe_node_ids_remain_exact_while_display_metadata_is_bounded() -> None:
    prefix = "test_bounds.py::test_value["
    node_id = prefix + ("x" * (MAX_NODE_ID_BYTES - len(prefix) - 1)) + "]"
    oversized_metadata = "m" * (MAX_METADATA_BYTES + 100)
    emitted: list[tuple[str, dict[str, Any]]] = []
    plugin = TrailheadPytestPlugin(
        lambda event_type, data: emitted.append((event_type, data)),
        "run",
        emit_collection=True,
    )
    session = _Session(
        [
            _Item(
                node_id,
                name=oversized_metadata,
                path=f"{oversized_metadata}.py",
                markers=(oversized_metadata,),
            )
        ]
    )

    plugin.pytest_collection_finish(cast(pytest.Session, session))
    plugin.pytest_runtest_logreport(
        _test_report(node_id, path=f"{oversized_metadata}.py")
    )
    plugin.pytest_runtest_logfinish(
        node_id,
        (f"{oversized_metadata}.py", 0, oversized_metadata),
    )

    collection = next(data for event, data in emitted if event == "TESTS_COLLECTED")
    collected = collection["tests"][0]
    assert collected["node_id"] == node_id
    assert len(collected["node_id"].encode("utf-8")) == MAX_NODE_ID_BYTES
    assert len(collected["name"].encode("utf-8")) <= MAX_METADATA_BYTES
    assert len(collected["path"].encode("utf-8")) <= MAX_METADATA_BYTES
    assert collected["markers"] == []
    assert set(collected["truncated"]) == {"name", "path", "markers"}

    result = next(data["test"] for event, data in emitted if event == "TEST_RESULT")
    assert result["node_id"] == node_id
    assert set(result["truncated"]) == {"name", "path", "markers"}
    assert (
        len(json.dumps(result, ensure_ascii=False).encode("utf-8"))
        < MAX_COLLECTION_BYTES
    )
    assert "path" in result["phases"][0]["truncated"]


def test_oversized_node_id_reports_bounded_omission_and_keeps_run_status() -> None:
    node_id = "x" * (MAX_NODE_ID_BYTES + 1)
    emitted: list[tuple[str, dict[str, Any]]] = []
    plugin = TrailheadPytestPlugin(
        lambda event_type, data: emitted.append((event_type, data)),
        "run",
        emit_collection=True,
    )
    session = _Session([_Item(node_id)])

    plugin.pytest_collection_finish(cast(pytest.Session, session))
    plugin.pytest_runtest_logreport(_test_report(node_id))
    plugin.pytest_runtest_logfinish(
        node_id,
        ("test_bounds.py", 0, "test_value"),
    )
    plugin.finish(pytest.ExitCode.OK)

    collection = next(data for event, data in emitted if event == "TESTS_COLLECTED")
    assert collection == {"tests": [], "total": 1, "truncated": True}
    errors = [data for event, data in emitted if event == "TEST_ERROR"]
    assert len(errors) == 1
    assert "result will be omitted" in errors[0]["message"]
    assert node_id not in json.dumps(emitted)
    assert not [data for event, data in emitted if event == "TEST_RESULT"]
    finished = next(data for event, data in emitted if event == "TEST_RUN_FINISHED")
    assert finished["status"] == "passed"
    assert finished["summary"]["total"] == 1
    assert finished["summary"]["passed"] == 1


def test_collection_budget_omission_keeps_safe_results_and_failed_status() -> None:
    node_ids: list[str] = []
    items: list[_Item] = []
    for index in range(80):
        prefix = f"test_many.py::test_value_{index}["
        node_id = prefix + ("x" * (8192 - len(prefix) - 1)) + "]"
        node_ids.append(node_id)
        items.append(_Item(node_id, name=f"test_value_{index}"))

    emitted: list[tuple[str, dict[str, Any]]] = []
    plugin = TrailheadPytestPlugin(
        lambda event_type, data: emitted.append((event_type, data)),
        "run",
        emit_collection=True,
    )
    session = _Session(items)
    plugin.pytest_collection_finish(cast(pytest.Session, session))

    collection = next(data for event, data in emitted if event == "TESTS_COLLECTED")
    displayed_node_ids = {
        test["node_id"] for test in cast(list[dict[str, Any]], collection["tests"])
    }
    omitted_node_id = node_ids[-1]
    assert collection["truncated"] is True
    assert len(displayed_node_ids) < len(node_ids)
    assert omitted_node_id not in displayed_node_ids
    assert (
        len(
            json.dumps(
                collection["tests"],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        <= MAX_COLLECTION_BYTES
    )

    plugin.pytest_runtest_logreport(_test_report(omitted_node_id, outcome="failed"))
    plugin.pytest_runtest_logfinish(
        omitted_node_id,
        ("test_many.py", 0, "test_value_79"),
    )
    plugin.finish(pytest.ExitCode.TESTS_FAILED)

    result = next(data["test"] for event, data in emitted if event == "TEST_RESULT")
    assert result["node_id"] == omitted_node_id
    assert result["outcome"] == "failed"
    finished = next(data for event, data in emitted if event == "TEST_RUN_FINISHED")
    assert finished["status"] == "failed"
    assert finished["summary"]["failed"] == 1


async def test_pytest_collection_error_is_structured_and_keeps_collection(
    tmp_path: Path,
) -> None:
    (tmp_path / "test_broken.py").write_text(
        "def test_broken(:\n    pass\n", encoding="utf-8"
    )

    return_code, socket = await _run_pytest(tmp_path, "test_broken", "collect")

    assert return_code != 0
    error = _events(socket, "TEST_ERROR")[0]
    assert error["kind"] == "collection"
    assert "SyntaxError" in error["details"]
    assert _events(socket, "TESTS_COLLECTED")[0]["tests"] == []
    finished = _events(socket, "TEST_RUN_FINISHED")[0]
    assert finished["status"] == "collection_error"


async def test_pytest_usage_error_has_diagnostic_and_one_terminal_event(
    tmp_path: Path,
) -> None:
    (tmp_path / "test_config.py").write_text(
        "def test_config():\n    pass\n", encoding="utf-8"
    )
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\naddopts = --trailhead-unknown-option\n", encoding="utf-8"
    )

    return_code, socket = await _run_pytest(tmp_path, "test_config", "collect")

    assert return_code == int(pytest.ExitCode.USAGE_ERROR)
    error = _events(socket, "TEST_ERROR")[0]
    assert error["kind"] == "usage"
    assert "unrecognized arguments" in error["details"]
    finished = _events(socket, "TEST_RUN_FINISHED")
    assert len(finished) == 1
    assert finished[0]["status"] == "usage_error"
    assert finished[0]["exit_code"] == int(pytest.ExitCode.USAGE_ERROR)


def test_collection_error_and_partial_items_are_both_emitted() -> None:
    from trailhead.pytest_plugin import TrailheadPytestPlugin

    emitted: list[tuple[str, dict[str, Any]]] = []
    plugin = TrailheadPytestPlugin(
        lambda event_type, data: emitted.append((event_type, data)), "collect"
    )

    class FailedReport:
        failed = True
        longrepr = "test_partial.py:9: collection failed"
        location = ("test_partial.py", 8, "test_partial")

    class Item:
        nodeid = "test_partial.py::test_collected"
        name = "test_collected"
        location = ("test_partial.py", 0, "test_collected")

        def iter_markers(self) -> list[object]:
            return []

    class Session:
        items = [Item()]

    plugin.pytest_collectreport(cast(pytest.CollectReport, FailedReport()))
    plugin.pytest_collection_finish(cast(pytest.Session, Session()))

    assert [event_type for event_type, _ in emitted] == [
        "TEST_ERROR",
        "TESTS_COLLECTED",
    ]
    assert emitted[1][1]["tests"][0]["node_id"] == ("test_partial.py::test_collected")


async def test_project_pytest_module_does_not_shadow_runtime_dependency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTHONPATH", ".")
    (tmp_path / "pytest.py").write_text(
        "raise AssertionError('student pytest.py was imported as pytest')\n",
        encoding="utf-8",
    )
    (tmp_path / "test_shadow.py").write_text(
        "def test_shadow():\n    assert True\n", encoding="utf-8"
    )

    return_code, socket = await _run_pytest(tmp_path, "test_shadow", "collect")

    assert return_code == 0
    assert _events(socket, "TESTS_COLLECTED")[0]["tests"][0]["name"] == "test_shadow"


async def test_deferred_pythonpath_remains_available_to_project_tests(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = tmp_path / "src"
    source_root.mkdir()
    (source_root / "project_support.py").write_text(
        "ANSWER = 42\n",
        encoding="utf-8",
    )
    (tmp_path / "test_src_layout.py").write_text(
        "from project_support import ANSWER\n"
        "\n"
        "def test_answer():\n"
        "    assert ANSWER == 42\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PYTHONPATH", "src")

    return_code, socket = await _run_pytest(
        tmp_path,
        "test_src_layout",
        "run",
    )

    assert return_code == int(pytest.ExitCode.OK)
    assert _events(socket, "TEST_RESULT")[0]["test"]["outcome"] == "passed"


async def test_late_pytest_shutdown_failure_is_terminal_internal_error(
    tmp_path: Path,
) -> None:
    (tmp_path / "test_late_failure.py").write_text(
        "def test_passes():\n    assert True\n",
        encoding="utf-8",
    )
    (tmp_path / "conftest.py").write_text(
        "def pytest_unconfigure(config):\n"
        "    raise RuntimeError('late pytest shutdown failure')\n",
        encoding="utf-8",
    )

    return_code, socket = await _run_pytest(
        tmp_path,
        "test_late_failure",
        "run",
    )

    assert return_code == int(pytest.ExitCode.INTERNAL_ERROR)
    finished = _events(socket, "TEST_RUN_FINISHED")
    assert len(finished) == 1
    assert finished[0]["exit_code"] == int(pytest.ExitCode.INTERNAL_ERROR)
    assert finished[0]["status"] == "internal_error"
    assert any(
        "late pytest shutdown failure"
        in (error.get("message", "") + error.get("details", ""))
        for error in _events(socket, "TEST_ERROR")
    )


async def test_cancelling_pytest_terminates_descendants(tmp_path: Path) -> None:
    sentinel = tmp_path / "descendant-survived"
    ready = tmp_path / "test-started"
    child_code = (
        "import time\n"
        "from pathlib import Path\n"
        "time.sleep(0.75)\n"
        f"Path({str(sentinel)!r}).write_text('survived', encoding='utf-8')\n"
    )
    (tmp_path / "test_slow.py").write_text(
        "import subprocess\n"
        "import sys\n"
        "import time\n"
        "from pathlib import Path\n"
        "\n"
        "def test_slow():\n"
        f"    Path({str(ready)!r}).write_text('ready', encoding='utf-8')\n"
        f"    subprocess.Popen([sys.executable, '-c', {child_code!r}])\n"
        "    time.sleep(30)\n",
        encoding="utf-8",
    )
    socket = RecordingSocket()
    process = AsyncPytestSubprocess(
        "test_slow",
        cast(WebSocket, socket),
        "cancel-1",
        "run",
        project_root=tmp_path,
    )
    pid = await process.start()
    await process.send_started(pid)

    try:
        for _ in range(1_000):
            if ready.exists():
                break
            await asyncio.sleep(0.01)
        else:
            raise AssertionError("pytest did not start the test")
        process.cancel()
        assert await asyncio.wait_for(process.await_end(), timeout=10) != 0
        await asyncio.sleep(1)
        assert not sentinel.exists()
        finished = _events(socket, "TEST_RUN_FINISHED")[-1]
        assert finished["status"] == "cancelled"
        assert finished["cancelled"] is True
    finally:
        process.kill()


async def test_pytest_websocket_is_reusable_and_validates_selected_node_ids(
    tmp_path: Path,
) -> None:
    (tmp_path / "test_selection.py").write_text(
        "import time\n"
        "\n"
        "def test_first():\n    assert True\n"
        "\n"
        "def test_second():\n    assert True\n"
        "\n"
        "def test_slow():\n    time.sleep(30)\n",
        encoding="utf-8",
    )
    set_project_root(tmp_path)
    socket = InteractiveSocket()
    handler = asyncio.create_task(
        pytest_websocket("test_selection", cast(WebSocket, socket))
    )

    try:
        await socket.command("TEST_COLLECT", "collect-1")
        collected = await _wait_for_event(socket, "TESTS_COLLECTED", "collect-1")
        await _wait_for_event(socket, "TEST_RUN_FINISHED", "collect-1")
        first_node_id = collected["tests"][0]["node_id"]
        slow_node_id = collected["tests"][2]["node_id"]

        await socket.command(
            "TEST_RUN",
            "invalid-1",
            node_ids=["another_module.py::test_first"],
        )
        invalid = await _wait_for_event(socket, "TEST_ERROR", "invalid-1")
        assert invalid["kind"] == "validation"
        assert "latest collection" in invalid["message"]

        await socket.command("TEST_RUN", "run-1", node_ids=[first_node_id])
        result = await _wait_for_event(socket, "TEST_RESULT", "run-1")
        finished = await _wait_for_event(socket, "TEST_RUN_FINISHED", "run-1")
        assert result["test"]["node_id"] == first_node_id
        assert finished["summary"]["total"] == 1
        assert finished["summary"]["passed"] == 1
        assert not [
            message
            for message in socket.messages
            if message["type"] == "TESTS_COLLECTED"
            and message["data"]["run_id"] == "run-1"
        ]

        await socket.command("TEST_RUN", "slow-1", node_ids=[slow_node_id])
        await _wait_for_event(socket, "TEST_RUN_STARTED", "slow-1")
        await socket.command("TEST_RUN", "busy-1")
        busy = await _wait_for_event(socket, "TEST_ERROR", "busy-1")
        assert "already active" in busy["message"]
        await socket.command("TEST_CANCEL", "wrong-run")
        wrong_cancel = await _wait_for_event(socket, "TEST_ERROR", "wrong-run")
        assert "different run_id" in wrong_cancel["message"]
        await socket.command("TEST_CANCEL", "slow-1")
        cancelled = await _wait_for_event(socket, "TEST_RUN_FINISHED", "slow-1")
        assert cancelled["cancelled"] is True
        assert (
            len(
                [
                    message
                    for message in socket.messages
                    if message["type"] == "TEST_RUN_FINISHED"
                    and message["data"]["run_id"] == "slow-1"
                ]
            )
            == 1
        )
    finally:
        await socket.disconnect()
        await asyncio.wait_for(handler, timeout=10)


async def test_run_all_refreshes_the_selectable_node_ids(tmp_path: Path) -> None:
    module = tmp_path / "test_refresh.py"
    module.write_text(
        "def test_old():\n    assert True\n",
        encoding="utf-8",
    )
    set_project_root(tmp_path)
    socket = InteractiveSocket()
    handler = asyncio.create_task(
        pytest_websocket("test_refresh", cast(WebSocket, socket))
    )

    try:
        await socket.command("TEST_COLLECT", "collect-1")
        initial = await _wait_for_event(socket, "TESTS_COLLECTED", "collect-1")
        await _wait_for_event(socket, "TEST_RUN_FINISHED", "collect-1")
        old_node_id = initial["tests"][0]["node_id"]

        module.write_text(
            "# refreshed source has a distinct bytecode-cache size\n"
            "def test_new():\n    assert True\n",
            encoding="utf-8",
        )
        await socket.command("TEST_RUN", "run-all")
        refreshed = await _wait_for_event(socket, "TESTS_COLLECTED", "run-all")
        await _wait_for_event(socket, "TEST_RUN_FINISHED", "run-all")
        new_node_id = refreshed["tests"][0]["node_id"]
        assert new_node_id.endswith("::test_new")

        await socket.command("TEST_RUN", "run-new", node_ids=[new_node_id])
        selected = await _wait_for_event(socket, "TEST_RESULT", "run-new")
        await _wait_for_event(socket, "TEST_RUN_FINISHED", "run-new")
        assert selected["test"]["node_id"] == new_node_id

        await socket.command("TEST_RUN", "run-old", node_ids=[old_node_id])
        rejected = await _wait_for_event(socket, "TEST_ERROR", "run-old")
        assert rejected["kind"] == "validation"
    finally:
        await socket.disconnect()
        await asyncio.wait_for(handler, timeout=10)
