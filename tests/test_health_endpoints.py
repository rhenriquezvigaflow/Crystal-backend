from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import health as health_module
from app.routers.health import router as health_router


class _DummySession:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    def execute(self, _query):
        if self.should_fail:
            raise RuntimeError("db down")
        return 1

    def close(self) -> None:
        return None


class _DummyWsManager:
    def stats(self) -> dict[str, object]:
        return {
            "lagoon_count": 1,
            "total_connections": 2,
            "connections_by_lagoon": {"lagoon-1": 2},
        }


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(health_router)
    app.state.ws_manager = _DummyWsManager()
    app.state.scada_watchdog = object()
    app.state.alarm_lagoon_signal_monitor = object()
    return app


def test_health_ready_reports_runtime_and_ws_stats(monkeypatch):
    monkeypatch.setattr(health_module, "SessionLocal", lambda: _DummySession())
    monkeypatch.setattr(
        health_module,
        "get_runtime_metrics",
        lambda: {
            "last_ingest_utc": datetime(2026, 4, 11, 18, 0, tzinfo=timezone.utc),
            "last_lagoon": "lagoon-1",
            "last_minute_rows": 14,
            "last_event_count": 2,
        },
    )

    client = TestClient(_build_app())
    response = client.get("/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["checks"]["database"] == "ok"
    assert payload["runtime"]["last_lagoon"] == "lagoon-1"
    assert payload["runtime"]["last_minute_rows"] == 14
    assert payload["websocket"]["total_connections"] == 2


def test_health_ready_returns_503_when_database_is_down(monkeypatch):
    monkeypatch.setattr(
        health_module,
        "SessionLocal",
        lambda: _DummySession(should_fail=True),
    )
    monkeypatch.setattr(
        health_module,
        "get_runtime_metrics",
        lambda: {
            "last_ingest_utc": None,
            "last_lagoon": None,
            "last_minute_rows": 0,
            "last_event_count": 0,
        },
    )

    client = TestClient(_build_app())
    response = client.get("/health/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["checks"]["database"] == "down"
