from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.jwt import get_current_user
from app.routers import email as email_router_module
from app.routers.email import router as email_router


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(email_router)
    app.dependency_overrides[get_current_user] = (
        lambda: {
            "sub": "user-1",
            "email": "user-1@local.test",
            "roles": ["AdminSmall"],
        }
    )
    return app


def test_email_test_alert_endpoint_queues_job(monkeypatch):
    queued_jobs = []

    monkeypatch.setattr(
        email_router_module.notification_orchestrator,
        "email_service",
        SimpleNamespace(is_configured=True),
    )

    monkeypatch.setattr(
        email_router_module,
        "dispatch_notifications",
        lambda jobs: queued_jobs.extend(jobs),
    )

    client = TestClient(_build_app())
    response = client.post(
        "/email/test-alert",
        json={
            "lagoon_id": "kirah",
            "plant_name": "Kirah Plant",
            "priority": "critical",
            "category": "state",
            "title": "Pump Fault",
            "description": "Pump 1 entered fault state",
            "recipients": ["ops@example.com"],
        },
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["ok"] is True
    assert payload["queued"] is True
    assert len(queued_jobs) == 1
    assert queued_jobs[0].channel == "email"


def test_email_test_alert_endpoint_requires_smtp_config(monkeypatch):
    monkeypatch.setattr(
        email_router_module.notification_orchestrator,
        "email_service",
        SimpleNamespace(is_configured=False),
    )

    client = TestClient(_build_app())
    response = client.post(
        "/email/test-alert",
        json={
            "lagoon_id": "kirah",
            "plant_name": "Kirah Plant",
            "priority": "warning",
            "category": "manual",
            "title": "Manual Alert",
            "description": "Manual test alert",
            "recipients": ["ops@example.com"],
        },
    )

    assert response.status_code == 503
