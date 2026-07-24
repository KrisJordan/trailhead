from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import socket
from typing import Any, cast

import pytest
import uvicorn
import websockets
from websockets.exceptions import ConnectionClosedError

from trailhead.app import app
from trailhead.project import set_project_root
from trailhead.websocket_origin import ALLOWED_ORIGINS_ENV


async def test_uvicorn_serves_a_real_websocket(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Exercise Uvicorn's optional WebSocket protocol on a real TCP socket."""

    (tmp_path / "example.py").write_text(
        'print("websocket relay works")\n', encoding="utf-8"
    )
    set_project_root(tmp_path)
    monkeypatch.delenv(ALLOWED_ORIGINS_ENV, raising=False)

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        listener.bind(("127.0.0.1", 0))
    except PermissionError:
        listener.close()
        pytest.skip("the execution sandbox does not permit local TCP listeners")
    listener.listen()
    listener.setblocking(False)
    port = listener.getsockname()[1]

    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    )
    server_task = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        for _ in range(500):
            if server.started:
                break
            if server_task.done():
                await server_task
                raise AssertionError("Uvicorn exited before accepting connections")
            await asyncio.sleep(0.01)
        else:
            raise AssertionError("Uvicorn did not start")

        async with websockets.connect(f"ws://127.0.0.1:{port}/ws") as websocket:
            await websocket.send('{"type":"LS","data":{}}')
            response: dict[str, Any] = json.loads(await websocket.recv())

        assert response["type"] == "LS"
        assert response["data"]["files"]["children"][0]["full_path"] == "./example.py"

        async with websockets.connect(
            f"ws://127.0.0.1:{port}/ws/example/run",
            origin=cast(Any, f"http://127.0.0.1:{port}"),
        ) as websocket:
            run_messages: list[dict[str, Any]] = []
            try:
                while True:
                    run_messages.append(json.loads(await websocket.recv()))
            except websockets.exceptions.ConnectionClosedOK:
                pass
        assert [message["type"] for message in run_messages] == [
            "RUNNING",
            "STDOUT",
            "EXIT",
        ]
        assert run_messages[1]["data"]["data"] == f"websocket relay works{os.linesep}"

        for path in ("/ws", "/ws/example/run"):
            with pytest.raises(websockets.exceptions.InvalidHandshake):
                async with websockets.connect(
                    f"ws://127.0.0.1:{port}{path}",
                    origin=cast(Any, "https://attacker.example"),
                ):
                    pass

        monkeypatch.setenv(
            ALLOWED_ORIGINS_ENV,
            "https://classroom.example",
        )
        async with websockets.connect(
            f"ws://127.0.0.1:{port}/ws",
            origin=cast(Any, "https://classroom.example"),
        ) as websocket:
            await websocket.send('{"type":"LS","data":{}}')
            configured_response: dict[str, Any] = json.loads(await websocket.recv())
        assert configured_response["type"] == "LS"

        async with websockets.connect(
            f"ws://127.0.0.1:{port}/ws/not_a_project_module/run"
        ) as websocket:
            with pytest.raises(ConnectionClosedError) as closed:
                await websocket.recv()
        assert closed.value.rcvd is not None
        assert closed.value.rcvd.code == 1008
    finally:
        server.should_exit = True
        await asyncio.wait_for(server_task, timeout=10)
        listener.close()
