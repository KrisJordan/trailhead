from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from fastapi import WebSocket

from trailhead.controller import web_socket_controller
from trailhead.project import set_project_root
from trailhead.web_socket_event import WebSocketEvent


class RecordingSocket:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def send_text(self, data: str) -> None:
        self.messages.append(json.loads(data))


async def test_controller_rejects_run_outside_project(tmp_path: Path) -> None:
    set_project_root(tmp_path)
    socket = RecordingSocket()

    await web_socket_controller(
        cast(WebSocket, socket),
        WebSocketEvent(
            type="RUN", data={"module": "missing", "request_id": "request-1"}
        ),
    )

    assert socket.messages == [
        {
            "type": "ERROR",
            "data": {"message": "Module not found", "request_id": "request-1"},
        }
    ]
