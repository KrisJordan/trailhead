from __future__ import annotations

from typing import Any, cast

import pytest
from starlette.types import Message, Receive, Scope, Send

from trailhead.websocket_origin import (
    ALLOWED_ORIGINS_ENV,
    WebSocketOriginMiddleware,
    add_allowed_websocket_origins,
    configured_websocket_origins,
    websocket_origin_is_allowed,
)


def websocket_scope(
    *,
    origin: str | None,
    host: str = "127.0.0.1:1110",
    scheme: str = "ws",
    path: str = "/ws",
    duplicate_origin: bool = False,
) -> Scope:
    headers = [(b"host", host.encode("ascii"))]
    if origin is not None:
        headers.append((b"origin", origin.encode("latin-1")))
        if duplicate_origin:
            headers.append((b"origin", origin.encode("latin-1")))
    return cast(
        Scope,
        {
            "type": "websocket",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "scheme": scheme,
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "root_path": "",
            "headers": headers,
            "client": ("127.0.0.1", 50000),
            "server": ("127.0.0.1", 1110),
            "subprotocols": [],
            "state": {},
            "extensions": {},
        },
    )


def test_non_browser_client_without_origin_is_allowed(monkeypatch: Any) -> None:
    monkeypatch.delenv(ALLOWED_ORIGINS_ENV, raising=False)
    assert websocket_origin_is_allowed(websocket_scope(origin=None))


@pytest.mark.parametrize(
    ("origin", "host", "scheme"),
    [
        ("http://127.0.0.1:8765", "127.0.0.1:8765", "ws"),
        ("http://localhost:1110", "localhost:1110", "ws"),
        ("http://[::1]:1110", "[::1]:1110", "ws"),
        ("https://localhost", "localhost", "wss"),
    ],
)
def test_loopback_same_origin_browser_is_allowed(
    monkeypatch: Any, origin: str, host: str, scheme: str
) -> None:
    monkeypatch.delenv(ALLOWED_ORIGINS_ENV, raising=False)
    assert websocket_origin_is_allowed(
        websocket_scope(origin=origin, host=host, scheme=scheme)
    )


def test_vite_proxy_with_browser_authority_is_allowed(monkeypatch: Any) -> None:
    monkeypatch.delenv(ALLOWED_ORIGINS_ENV, raising=False)
    assert websocket_origin_is_allowed(
        websocket_scope(origin="http://localhost:1110", host="localhost:1110")
    )


@pytest.mark.parametrize(
    ("origin", "host"),
    [
        ("https://attacker.example", "127.0.0.1:1110"),
        # Matching an attacker-controlled Host is not enough: this is the shape
        # of a DNS-rebinding request and neither side is a loopback identity.
        ("http://attacker.example:1110", "attacker.example:1110"),
        ("http://localhost:3000", "127.0.0.1:1109"),
        ("http://localhost:1110", "127.0.0.1:9999"),
        ("null", "127.0.0.1:1110"),
        ("ws://127.0.0.1:1110", "127.0.0.1:1110"),
    ],
)
def test_untrusted_browser_origins_are_rejected(
    monkeypatch: Any, origin: str, host: str
) -> None:
    monkeypatch.delenv(ALLOWED_ORIGINS_ENV, raising=False)
    assert not websocket_origin_is_allowed(websocket_scope(origin=origin, host=host))


def test_duplicate_origin_headers_are_rejected(monkeypatch: Any) -> None:
    monkeypatch.delenv(ALLOWED_ORIGINS_ENV, raising=False)
    assert not websocket_origin_is_allowed(
        websocket_scope(
            origin="http://127.0.0.1:1110",
            duplicate_origin=True,
        )
    )


def test_exact_configured_origins_support_lan_and_https(monkeypatch: Any) -> None:
    monkeypatch.setenv(
        ALLOWED_ORIGINS_ENV,
        "https://Classroom.Example:443/,http://192.168.1.25:1110",
    )

    assert websocket_origin_is_allowed(
        websocket_scope(origin="https://classroom.example")
    )
    assert websocket_origin_is_allowed(
        websocket_scope(origin="http://192.168.1.25:1110")
    )
    assert not websocket_origin_is_allowed(
        websocket_scope(origin="https://subdomain.classroom.example")
    )


@pytest.mark.parametrize(
    "configured",
    [
        "*",
        "null",
        "https://*.example.com",
        "ws://localhost:1110",
        "http://localhost:1110/path",
        "http://user@localhost:1110",
        "http://localhost:not-a-port",
    ],
)
def test_invalid_configured_origins_are_rejected(
    monkeypatch: Any, configured: str
) -> None:
    monkeypatch.setenv(ALLOWED_ORIGINS_ENV, configured)
    with pytest.raises(ValueError):
        configured_websocket_origins()


def test_cli_origin_helper_canonicalizes_and_adds_to_environment(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv(ALLOWED_ORIGINS_ENV, "http://localhost:3000")
    add_allowed_websocket_origins(["HTTPS://Classroom.Example:443/"])
    assert os_environ_value() == ("http://localhost:3000,https://classroom.example")


def os_environ_value() -> str:
    # A helper keeps the environment lookup typed as str for static analysis on all
    # supported Python versions.
    import os

    return os.environ[ALLOWED_ORIGINS_ENV]


@pytest.mark.parametrize(
    "path",
    [
        "/ws",
        "/ws/example/run",
        "/ws/example/repl",
        "/ws/example/repl_gui",
    ],
)
async def test_middleware_rejects_untrusted_origin_before_every_endpoint(
    monkeypatch: Any, path: str
) -> None:
    monkeypatch.delenv(ALLOWED_ORIGINS_ENV, raising=False)
    called = False
    sent: list[Message] = []

    async def downstream(scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal called
        called = True

    async def receive() -> Message:
        return {"type": "websocket.connect"}

    async def send(message: Message) -> None:
        sent.append(message)

    middleware = WebSocketOriginMiddleware(downstream)
    await middleware(
        websocket_scope(
            origin="https://attacker.example",
            host="127.0.0.1:1110",
            path=path,
        ),
        receive,
        send,
    )

    assert not called
    assert sent == [
        {
            "type": "websocket.close",
            "code": 1008,
            "reason": "WebSocket origin is not allowed",
        }
    ]
