from __future__ import annotations

import pytest
from fastapi import WebSocketException
from starlette.datastructures import QueryParams, URL

from app.routers import websocket as websocket_router
from app.security import rbac


class _DummyWebSocket:
    def __init__(
        self,
        *,
        headers: dict[str, str] | None = None,
        query_params: dict[str, str] | None = None,
        url: str = "ws://127.0.0.1:8090/ws/scada/demo",
    ) -> None:
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.query_params = QueryParams(query_params or {})
        self.url = URL(url)


def test_extract_websocket_token_from_subprotocol(monkeypatch):
    monkeypatch.setattr(rbac.settings, "WS_ALLOW_QUERY_TOKEN", False)
    websocket = _DummyWebSocket(
        headers={
            "sec-websocket-protocol": "crystal-scada.v1, bearer.jwt-token-123",
        }
    )

    assert rbac.describe_websocket_token_source(websocket) == "subprotocol"
    assert rbac.extract_websocket_token(websocket) == "jwt-token-123"


def test_extract_websocket_token_rejects_query_when_disabled(monkeypatch):
    monkeypatch.setattr(rbac.settings, "WS_ALLOW_QUERY_TOKEN", False)
    websocket = _DummyWebSocket(query_params={"token": "legacy-query-token"})

    with pytest.raises(WebSocketException) as exc:
        rbac.extract_websocket_token(websocket)

    assert exc.value.reason == "Missing token"


def test_extract_websocket_token_accepts_query_when_enabled(monkeypatch):
    monkeypatch.setattr(rbac.settings, "WS_ALLOW_QUERY_TOKEN", True)
    websocket = _DummyWebSocket(query_params={"token": "legacy-query-token"})

    assert rbac.describe_websocket_token_source(websocket) == "query"
    assert rbac.extract_websocket_token(websocket) == "legacy-query-token"


def test_ws_origin_accepts_same_host_ip_even_if_not_whitelisted(monkeypatch):
    monkeypatch.setattr(
        websocket_router.settings,
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173",
    )
    monkeypatch.setattr(
        websocket_router.settings,
        "WS_ALLOWED_ORIGINS",
        "",
    )

    websocket = _DummyWebSocket(
        headers={
            "origin": "http://192.168.2.100:8085",
            "host": "192.168.2.100:8090",
        },
        url="ws://192.168.2.100:8090/ws/scada/demo",
    )

    assert websocket_router._is_origin_allowed_for_websocket(
        websocket,
        websocket.headers["origin"],
    )


def test_ws_origin_rejects_unknown_host_when_not_whitelisted(monkeypatch):
    monkeypatch.setattr(
        websocket_router.settings,
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173",
    )
    monkeypatch.setattr(
        websocket_router.settings,
        "WS_ALLOWED_ORIGINS",
        "",
    )

    websocket = _DummyWebSocket(
        headers={
            "origin": "http://10.0.0.55:3000",
            "host": "192.168.2.100:8090",
        },
        url="ws://192.168.2.100:8090/ws/scada/demo",
    )

    assert not websocket_router._is_origin_allowed_for_websocket(
        websocket,
        websocket.headers["origin"],
    )
