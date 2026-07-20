"""Origin validation for browser WebSocket connections.

The Origin header is a browser security boundary, not an authentication
mechanism.  Non-browser WebSocket clients commonly omit it, so requests without
an Origin remain supported.  When a browser supplies an Origin, Trailhead only
trusts its local, same-origin UI and the repository's standard Vite proxy unless
an administrator explicitly configures another exact origin.
"""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import os
from collections.abc import Iterable
from urllib.parse import urlsplit

from starlette.types import ASGIApp, Receive, Scope, Send

ALLOWED_ORIGINS_ENV = "TRAILHEAD_ALLOWED_ORIGINS"
"""Comma-separated browser origins that may connect to Trailhead."""

_DEFAULT_PORTS = {"http": 80, "https": 443}


@dataclass(frozen=True)
class _Origin:
    scheme: str
    host: str
    port: int

    def serialize(self) -> str:
        host = f"[{self.host}]" if ":" in self.host else self.host
        default_port = _DEFAULT_PORTS[self.scheme]
        port = "" if self.port == default_port else f":{self.port}"
        return f"{self.scheme}://{host}{port}"


def _normalize_host(host: str) -> str:
    """Return the canonical ASCII spelling of an IP address or DNS name."""

    host = host.lower().rstrip(".")
    if not host:
        raise ValueError("origin host must not be empty")
    try:
        return ipaddress.ip_address(host).compressed
    except ValueError:
        try:
            canonical = host.encode("idna").decode("ascii")
        except UnicodeError as error:
            raise ValueError(f"invalid origin host: {host!r}") from error
        if any(not label or len(label) > 63 for label in canonical.split(".")):
            raise ValueError(f"invalid origin host: {host!r}")
        return canonical


def _parse_origin(value: str) -> _Origin:
    """Parse and canonicalize one exact HTTP(S) browser Origin value."""

    value = value.strip()
    if not value or "*" in value:
        raise ValueError("an allowed origin must be an exact http(s) origin")
    if any(character.isspace() for character in value):
        raise ValueError(f"invalid origin: {value!r}")

    parsed = urlsplit(value)
    if parsed.scheme.lower() not in _DEFAULT_PORTS:
        raise ValueError(f"origin must use http or https: {value!r}")
    if not parsed.netloc or parsed.username is not None or parsed.password is not None:
        raise ValueError(f"invalid origin: {value!r}")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError(
            f"origin must not include a path, query, or fragment: {value!r}"
        )
    if parsed.hostname is None:
        raise ValueError(f"invalid origin: {value!r}")

    scheme = parsed.scheme.lower()
    try:
        parsed_port = parsed.port
    except ValueError as error:
        raise ValueError(f"invalid origin port: {value!r}") from error
    port = _DEFAULT_PORTS[scheme] if parsed_port is None else parsed_port
    return _Origin(scheme, _normalize_host(parsed.hostname), port)


def configured_websocket_origins() -> frozenset[_Origin]:
    """Return the exact origins configured through the environment."""

    raw = os.environ.get(ALLOWED_ORIGINS_ENV, "")
    values = [value.strip() for value in raw.split(",") if value.strip()]
    return frozenset(_parse_origin(value) for value in values)


def add_allowed_websocket_origins(origins: Iterable[str]) -> None:
    """Validate and add exact origins to the process/reload-worker environment."""

    configured = set(configured_websocket_origins())
    configured.update(_parse_origin(origin) for origin in origins)
    if configured:
        serialized = sorted(origin.serialize() for origin in configured)
        os.environ[ALLOWED_ORIGINS_ENV] = ",".join(serialized)


def _header_values(scope: Scope, name: bytes) -> list[str]:
    return [
        value.decode("latin-1")
        for header_name, value in scope.get("headers", [])
        if header_name.lower() == name
    ]


def _request_origin(scope: Scope) -> _Origin | None:
    origins = _header_values(scope, b"origin")
    if not origins:
        return None
    if len(origins) != 1:
        raise ValueError("multiple Origin headers are not allowed")
    return _parse_origin(origins[0])


def _request_authority(scope: Scope, scheme: str) -> _Origin:
    hosts = _header_values(scope, b"host")
    if len(hosts) != 1:
        raise ValueError("a single Host header is required")
    parsed = _parse_origin(f"{scheme}://{hosts[0]}")
    return parsed


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def websocket_origin_is_allowed(scope: Scope) -> bool:
    """Return whether a WebSocket scope satisfies Trailhead's Origin policy."""

    try:
        origin = _request_origin(scope)
        if origin is None:
            # Native/CLI WebSocket clients generally don't send Origin.  Origin
            # enforcement specifically protects browsers and isn't client auth.
            return True
        if origin in configured_websocket_origins():
            return True

        websocket_scheme = scope.get("scheme", "ws").lower()
        if websocket_scheme in ("ws", "http"):
            http_scheme = "http"
        elif websocket_scheme in ("wss", "https"):
            http_scheme = "https"
        else:
            return False
        target = _request_authority(scope, http_scheme)

        # The installed/built client is served from the same loopback origin.
        # Requiring loopback here also prevents DNS-rebinding origins from
        # becoming trusted merely because their attacker-controlled Host agrees.
        if origin == target and _is_loopback(origin.host):
            return True

        return False
    except (UnicodeError, ValueError):
        # Malformed or ambiguous browser security headers always fail closed.
        return False


class WebSocketOriginMiddleware:
    """Reject browser WebSockets with untrusted Origin headers before accept."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket" and not websocket_origin_is_allowed(scope):
            await send(
                {
                    "type": "websocket.close",
                    "code": 1008,
                    "reason": "WebSocket origin is not allowed",
                }
            )
            return
        await self.app(scope, receive, send)
