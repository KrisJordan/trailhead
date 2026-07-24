"""Long-lived WebSocket controller for structured pytest operations."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from pathlib import Path
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState

from .project import get_project_root, module_file
from .pytest_protocol import MAX_NODE_ID_BYTES
from .pytest_subprocess import AsyncPytestSubprocess
from .web_socket_event import WebSocketEvent

MAX_RUN_ID_LENGTH = 256


async def _send(client: WebSocket, event_type: str, run_id: str, **data: Any) -> None:
    await client.send_text(
        WebSocketEvent(
            type=event_type,
            data={"run_id": run_id, **data},
        ).model_dump_json()
    )


async def _send_error(
    client: WebSocket,
    run_id: str,
    message: str,
    *,
    kind: str = "validation",
) -> None:
    await _send(client, "TEST_ERROR", run_id, kind=kind, message=message)


def _run_id(data: dict[str, Any]) -> str | None:
    value = data.get("run_id")
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > MAX_RUN_ID_LENGTH
    ):
        return None
    return value


def _selected_node_ids(data: dict[str, Any]) -> tuple[str, ...] | None:
    value = data.get("node_ids")
    if value is None:
        return ()
    if not isinstance(value, list):
        return None
    node_ids: list[str] = []
    for node_id in value:
        if (
            not isinstance(node_id, str)
            or not node_id
            or (len(node_id.encode("utf-8", errors="replace")) > MAX_NODE_ID_BYTES)
        ):
            return None
        node_ids.append(node_id)
    return tuple(node_ids)


async def _start(
    module: str,
    client: WebSocket,
    run_id: str,
    mode: str,
    node_ids: tuple[str, ...],
    project_root: Path,
) -> tuple[AsyncPytestSubprocess, asyncio.Task[int]] | None:
    process = AsyncPytestSubprocess(
        module,
        client,
        run_id,
        mode,
        node_ids,
        project_root,
    )
    try:
        pid = await process.start()
        await process.send_started(pid)
    except (OSError, RuntimeError) as error:
        process.kill()
        await _send_error(
            client,
            run_id,
            f"Unable to start pytest: {error}",
            kind="internal",
        )
        await _send(
            client,
            "TEST_RUN_FINISHED",
            run_id,
            exit_code=None,
            status="internal_error",
            duration=0.0,
            summary={
                "total": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "xfailed": 0,
                "xpassed": 0,
                "error": 0,
            },
            cancelled=False,
        )
        return None
    return process, asyncio.create_task(process.await_end())


async def pytest_websocket(module: str, client: WebSocket) -> None:
    """Collect and run a module's pytest cases over one reusable connection."""

    await client.accept()
    project_root = get_project_root()
    try:
        path = module_file(module, project_root)
    except ValueError:
        path = None
    if path is None or not path.is_file():
        await client.close(code=1008, reason="Module not found")
        return

    active: AsyncPytestSubprocess | None = None
    completion: asyncio.Task[int] | None = None
    receive: asyncio.Task[str] | None = asyncio.create_task(client.receive_text())
    collected_node_ids: set[str] = set()

    try:
        while receive is not None:
            pending: set[asyncio.Task[Any]] = {receive}
            if completion is not None:
                pending.add(completion)
            done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)

            if completion is not None and completion in done:
                with suppress(Exception):
                    await completion
                if active is not None and (
                    active.mode == "collect" or not active.node_ids
                ):
                    collected_node_ids = active.collected_node_ids
                completion = None
                active = None

            if receive not in done:
                continue

            raw_event = await receive
            receive = asyncio.create_task(client.receive_text())
            if completion is not None and completion.done():
                with suppress(Exception):
                    await completion
                if active is not None and (
                    active.mode == "collect" or not active.node_ids
                ):
                    collected_node_ids = active.collected_node_ids
                completion = None
                active = None
            try:
                event = WebSocketEvent.model_validate_json(raw_event)
            except ValueError:
                await _send_error(
                    client, "", "Unable to parse pytest command", kind="protocol"
                )
                continue

            run_id = _run_id(event.data)
            if run_id is None:
                await _send_error(
                    client,
                    "",
                    "Every pytest command requires a non-empty run_id",
                    kind="protocol",
                )
                continue

            if event.type == "TEST_CANCEL":
                if active is None or completion is None:
                    await _send_error(client, run_id, "No pytest run is active")
                elif active.run_id != run_id:
                    await _send_error(
                        client,
                        run_id,
                        "The active pytest run has a different run_id",
                    )
                else:
                    active.cancel()
                continue

            if event.type not in {"TEST_COLLECT", "TEST_RUN"}:
                await _send_error(
                    client,
                    run_id,
                    f"Unsupported pytest command: {event.type}",
                    kind="protocol",
                )
                continue

            if active is not None or completion is not None:
                await _send_error(client, run_id, "A pytest run is already active")
                continue

            node_ids: tuple[str, ...] = ()
            if event.type == "TEST_RUN":
                selected = _selected_node_ids(event.data)
                if selected is None:
                    await _send_error(client, run_id, "node_ids must be a string list")
                    continue
                invalid = [
                    node_id for node_id in selected if node_id not in collected_node_ids
                ]
                if invalid:
                    await _send_error(
                        client,
                        run_id,
                        "Selected tests must come from the latest collection",
                    )
                    continue
                node_ids = selected

            started = await _start(
                module,
                client,
                run_id,
                "collect" if event.type == "TEST_COLLECT" else "run",
                node_ids,
                project_root,
            )
            if started is not None:
                active, completion = started
    except WebSocketDisconnect:
        pass
    finally:
        if receive is not None:
            receive.cancel()
            with suppress(asyncio.CancelledError, WebSocketDisconnect):
                await receive
        if active is not None:
            active.cancel()
        if completion is not None:
            with suppress(Exception):
                await asyncio.shield(completion)
        if client.client_state == WebSocketState.CONNECTED:
            await client.close()
