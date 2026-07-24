"""Structured pytest child process built on Trailhead's portable runner."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import subprocess
import time
from typing import Any

from fastapi import WebSocket

from .async_python_subprocess import AsyncPythonSubprocess
from .pytest_protocol import EVENT_PREFIX, limited_text
from .web_socket_event import WebSocketEvent

_CHILD_EVENT_TYPES = {
    "TESTS_COLLECTED",
    "TEST_RESULT",
    "TEST_RUN_FINISHED",
    "TEST_ERROR",
}


def _exit_status(return_code: int | None) -> tuple[str, str]:
    """Return the terminal status and diagnostic kind for a child exit."""

    return {
        0: ("passed", "internal"),
        1: ("failed", "test"),
        2: ("interrupted", "internal"),
        3: ("internal_error", "internal"),
        4: ("usage_error", "usage"),
        5: ("no_tests", "usage"),
    }.get(
        return_code if return_code is not None else -1,
        ("internal_error", "internal"),
    )


class AsyncPytestSubprocess(AsyncPythonSubprocess):
    """Decode structured child events without duplicating process management."""

    def __init__(
        self,
        module: str,
        client: WebSocket,
        run_id: str,
        mode: str,
        node_ids: tuple[str, ...] = (),
        project_root: Path | None = None,
    ) -> None:
        super().__init__(
            module,
            client,
            "trailhead.wrappers.pytest",
            project_root,
            (mode, *node_ids),
            include_project_import_path=False,
        )
        self.run_id = run_id
        self.mode = mode
        self.node_ids = node_ids
        self._started_at = time.monotonic()
        self._finished = False
        self._finish_data: dict[str, Any] | None = None
        self._cancelled = False
        self._unexpected_output = ""
        self._saw_error = False
        self._started = asyncio.Event()
        self.collected_node_ids: set[str] = set()

    def cancel(self) -> None:
        """Mark this run cancelled before terminating its full process tree."""

        self._cancelled = True
        self.kill()

    async def send_started(self, pid: int) -> None:
        try:
            await self._send(
                "TEST_RUN_STARTED",
                {
                    "mode": self.mode,
                    "node_ids": list(self.node_ids),
                    "pid": pid,
                },
            )
        finally:
            self._started.set()

    async def _send(self, event_type: str, data: dict[str, Any]) -> None:
        await self._client.send_text(
            WebSocketEvent(
                type=event_type,
                data={"run_id": self.run_id, **data},
            ).model_dump_json()
        )

    async def _handle_stdout(
        self,
        output: str,
        is_prompt: bool,
        process: subprocess.Popen[bytes],
    ) -> None:
        del is_prompt, process
        prefix_index = output.find(EVENT_PREFIX)
        if prefix_index < 0:
            self._remember_unexpected(output)
            return
        if prefix_index:
            self._remember_unexpected(output[:prefix_index])
        await self._started.wait()
        try:
            event = json.loads(output[prefix_index + len(EVENT_PREFIX) :])
            event_type = event["type"]
            data = event["data"]
            if event_type not in _CHILD_EVENT_TYPES or not isinstance(data, dict):
                raise ValueError("unsupported child event")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            await self._send(
                "TEST_ERROR",
                {
                    "kind": "protocol",
                    "message": f"Invalid pytest child event: {error}",
                },
            )
            return
        if event_type == "TEST_RUN_FINISHED":
            self._finish_data = data
            return
        elif event_type == "TESTS_COLLECTED":
            tests = data.get("tests")
            if isinstance(tests, list):
                self.collected_node_ids = {
                    test["node_id"]
                    for test in tests
                    if isinstance(test, dict) and isinstance(test.get("node_id"), str)
                }
        elif event_type == "TEST_RESULT":
            test = data.get("test")
            if isinstance(test, dict) and isinstance(test.get("node_id"), str):
                self.collected_node_ids.add(test["node_id"])
        elif event_type == "TEST_ERROR":
            self._saw_error = True
        await self._send(event_type, data)

    async def _handle_stderr(
        self, output: str, process: subprocess.Popen[bytes]
    ) -> None:
        del process
        self._remember_unexpected(output)

    async def _handle_exit(self, process: subprocess.Popen[bytes]) -> None:
        if self._finish_data is not None:
            finish_data = dict(self._finish_data)
            reported_exit_code = finish_data.get("exit_code")
            actual_exit_code = process.returncode
            if self._cancelled:
                finish_data.update(
                    {
                        "exit_code": actual_exit_code,
                        "status": "cancelled",
                        "cancelled": True,
                    }
                )
            elif reported_exit_code != actual_exit_code:
                status, error_kind = _exit_status(actual_exit_code)
                await self._send(
                    "TEST_ERROR",
                    {
                        "kind": error_kind,
                        "message": (
                            "Pytest exited after its session report with "
                            f"status {actual_exit_code}"
                        ),
                        "details": (
                            "The final process exit code did not match pytest's "
                            f"session result ({reported_exit_code})."
                        ),
                    },
                )
                finish_data.update(
                    {
                        "exit_code": actual_exit_code,
                        "status": status,
                        "cancelled": False,
                    }
                )
            elif not self._saw_error and finish_data.get("status") in {
                "internal_error",
                "interrupted",
                "usage_error",
            }:
                details, was_truncated = limited_text(self._unexpected_output)
                _, error_kind = _exit_status(actual_exit_code)
                await self._send(
                    "TEST_ERROR",
                    {
                        "kind": error_kind,
                        "message": (
                            "Pytest could not complete the requested operation"
                        ),
                        "details": details,
                        "truncated": ["details"] if was_truncated else [],
                    },
                )
            await self._send("TEST_RUN_FINISHED", finish_data)
            self._finished = True
            return

        return_code = process.returncode
        status, error_kind = _exit_status(return_code)
        if return_code in {0, 1}:
            # A normal pass/fail always comes with the plugin's structured
            # terminal record. Exiting without it is a protocol failure.
            status, error_kind = "internal_error", "internal"
        if not self._cancelled:
            details, was_truncated = limited_text(self._unexpected_output)
            await self._send(
                "TEST_ERROR",
                {
                    "kind": error_kind,
                    "message": (
                        "Pytest exited before completing its structured report"
                    ),
                    "details": details,
                    "truncated": ["details"] if was_truncated else [],
                },
            )
        await self._send(
            "TEST_RUN_FINISHED",
            {
                "exit_code": return_code,
                "status": "cancelled" if self._cancelled else status,
                "duration": time.monotonic() - self._started_at,
                "summary": {
                    "total": 0,
                    "passed": 0,
                    "failed": 0,
                    "skipped": 0,
                    "xfailed": 0,
                    "xpassed": 0,
                    "error": 0,
                },
                "cancelled": self._cancelled,
            },
        )
        self._finished = True

    def _remember_unexpected(self, output: str) -> None:
        if len(self._unexpected_output) < 64 * 1024:
            self._unexpected_output += output
