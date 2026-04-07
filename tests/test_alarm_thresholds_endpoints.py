from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.alarms.thresholds.schemas import (
    ThresholdViewRowOut,
)
from app.alarms.thresholds.service import AlarmThresholdService
from app.auth.jwt import get_current_user
from app.db.session import get_db
from app.routers import alarm_thresholds as alarm_thresholds_router_module
from app.routers.alarm_thresholds import router as alarm_thresholds_router


class _DummyDB:
    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


def _build_app(with_auth_override: bool, user_payload: dict | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(alarm_thresholds_router)
    app.include_router(alarm_thresholds_router, prefix="/crystal")
    app.include_router(alarm_thresholds_router, prefix="/small")
    app.include_router(alarm_thresholds_router, prefix="/api")
    app.include_router(alarm_thresholds_router, prefix="/api/crystal")
    app.include_router(alarm_thresholds_router, prefix="/api/small")

    def _override_db():
        yield _DummyDB()

    app.dependency_overrides[get_db] = _override_db

    if with_auth_override:
        app.dependency_overrides[get_current_user] = (
            lambda: user_payload
            or {
                "sub": "user-1",
                "email": "user-1@local.test",
                "roles": ["AdminSmall"],
            }
        )

    return app


def test_get_thresholds_view_base_and_alias_routes(monkeypatch):
    monkeypatch.setattr(
        alarm_thresholds_router_module,
        "ensure_lagoon_access",
        lambda **kwargs: None,
    )

    def _fake_get_thresholds_view(db, lagoon_id: str):
        assert lagoon_id == "costa_del_lago"
        return [
            ThresholdViewRowOut(
                tag_id="PT117_R_SCADA",
                tag_name="PT 117 Retorno",
                source="configured",
                min_value=1.2,
                max_value=8.5,
                severity="critical",
                enabled=True,
            )
        ]

    monkeypatch.setattr(
        AlarmThresholdService,
        "get_thresholds_view",
        staticmethod(_fake_get_thresholds_view),
    )

    client = TestClient(_build_app(with_auth_override=True))

    paths = [
        "/alarms/costa_del_lago/thresholds/pt-fit/view",
        "/crystal/alarms/costa_del_lago/thresholds/pt-fit/view",
        "/small/alarms/costa_del_lago/thresholds/pt-fit/view",
        "/api/alarms/costa_del_lago/thresholds/pt-fit/view",
        "/api/crystal/alarms/costa_del_lago/thresholds/pt-fit/view",
        "/api/small/alarms/costa_del_lago/thresholds/pt-fit/view",
    ]
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200
        payload = response.json()
        assert payload["lagoon_id"] == "costa_del_lago"
        assert payload["rows"][0]["tag_id"] == "PT117_R_SCADA"
        assert payload["rows"][0]["source"] == "configured"


def test_put_upsert_thresholds_ok(monkeypatch):
    monkeypatch.setattr(
        alarm_thresholds_router_module,
        "ensure_lagoon_access",
        lambda **kwargs: None,
    )

    def _fake_upsert(db, lagoon_id: str, payload):
        assert lagoon_id == "costa_del_lago"
        assert len(payload.items) == 1
        assert payload.items[0].tag_id == "PT117_R_SCADA"
        return (
            ["threshold_pt117_r_scada_min"],
            ["threshold_pt117_r_scada_max"],
        )

    monkeypatch.setattr(
        AlarmThresholdService,
        "upsert_thresholds",
        staticmethod(_fake_upsert),
    )

    client = TestClient(_build_app(with_auth_override=True))

    response = client.put(
        "/alarms/costa_del_lago/thresholds/pt-fit",
        json={
            "items": [
                {
                    "tag_id": "PT117_R_SCADA",
                    "min_value": 1.2,
                    "max_value": 8.5,
                    "severity": "critical",
                    "enabled": True,
                }
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["lagoon_id"] == "costa_del_lago"
    assert payload["created"] == ["threshold_pt117_r_scada_min"]
    assert payload["updated"] == ["threshold_pt117_r_scada_max"]


def test_put_upsert_thresholds_ok_alias_crystal(monkeypatch):
    monkeypatch.setattr(
        alarm_thresholds_router_module,
        "ensure_lagoon_access",
        lambda **kwargs: None,
    )

    monkeypatch.setattr(
        AlarmThresholdService,
        "upsert_thresholds",
        staticmethod(lambda db, lagoon_id, payload: (["c1"], ["u1"])),
    )

    client = TestClient(_build_app(with_auth_override=True))
    response = client.put(
        "/crystal/alarms/costa_del_lago/thresholds/pt-fit",
        json={
            "items": [
                {
                    "tag_id": "FIT001_SCADA",
                    "max_value": 9.0,
                    "severity": "critical",
                    "enabled": True,
                }
            ]
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["created"] == ["c1"]
    assert payload["updated"] == ["u1"]


def test_put_upsert_thresholds_ok_alias_api_crystal(monkeypatch):
    monkeypatch.setattr(
        alarm_thresholds_router_module,
        "ensure_lagoon_access",
        lambda **kwargs: None,
    )

    monkeypatch.setattr(
        AlarmThresholdService,
        "upsert_thresholds",
        staticmethod(lambda db, lagoon_id, payload: (["c_api"], ["u_api"])),
    )

    client = TestClient(_build_app(with_auth_override=True))
    response = client.put(
        "/api/crystal/alarms/costa_del_lago/thresholds/pt-fit",
        json={
            "items": [
                {
                    "tag_id": "FIT001_SCADA",
                    "max_value": 9.0,
                    "severity": "critical",
                    "enabled": True,
                }
            ]
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["created"] == ["c_api"]
    assert payload["updated"] == ["u_api"]


def test_put_items_empty_returns_422(monkeypatch):
    monkeypatch.setattr(
        alarm_thresholds_router_module,
        "ensure_lagoon_access",
        lambda **kwargs: None,
    )

    client = TestClient(_build_app(with_auth_override=True))
    response = client.put(
        "/alarms/costa_del_lago/thresholds/pt-fit",
        json={"items": []},
    )
    assert response.status_code == 422


def test_put_invalid_tag_returns_422(monkeypatch):
    monkeypatch.setattr(
        alarm_thresholds_router_module,
        "ensure_lagoon_access",
        lambda **kwargs: None,
    )

    client = TestClient(_build_app(with_auth_override=True))
    response = client.put(
        "/alarms/costa_del_lago/thresholds/pt-fit",
        json={
            "items": [
                {
                    "tag_id": "VE123_ST",
                    "min_value": 1.0,
                    "severity": "warning",
                    "enabled": True,
                }
            ]
        },
    )
    assert response.status_code == 422
    assert "PT/FIT" in str(response.json())


def test_get_thresholds_view_without_token_returns_401():
    client = TestClient(_build_app(with_auth_override=False))
    response = client.get("/alarms/costa_del_lago/thresholds/pt-fit/view")
    assert response.status_code == 401


def test_get_thresholds_view_forbidden_role_returns_403():
    client = TestClient(
        _build_app(
            with_auth_override=True,
            user_payload={
                "sub": "user-2",
                "email": "user-2@local.test",
                "roles": ["UnknownRole"],
            },
        )
    )
    response = client.get("/alarms/costa_del_lago/thresholds/pt-fit/view")
    assert response.status_code == 403


def test_legacy_read_endpoints_removed_return_404():
    client = TestClient(_build_app(with_auth_override=True))
    removed_paths = [
        "/alarms/costa_del_lago/thresholds/pt-fit/candidates",
        "/crystal/alarms/costa_del_lago/thresholds/pt-fit/candidates",
        "/small/alarms/costa_del_lago/thresholds/pt-fit/candidates",
        "/api/alarms/costa_del_lago/thresholds/pt-fit/candidates",
        "/api/crystal/alarms/costa_del_lago/thresholds/pt-fit/candidates",
        "/api/small/alarms/costa_del_lago/thresholds/pt-fit/candidates",
    ]
    for path in removed_paths:
        response = client.get(path)
        assert response.status_code == 404

    # El path base se mantiene para PUT, por GET responde Method Not Allowed.
    method_not_allowed_paths = [
        "/alarms/costa_del_lago/thresholds/pt-fit",
        "/crystal/alarms/costa_del_lago/thresholds/pt-fit",
        "/small/alarms/costa_del_lago/thresholds/pt-fit",
        "/api/alarms/costa_del_lago/thresholds/pt-fit",
        "/api/crystal/alarms/costa_del_lago/thresholds/pt-fit",
        "/api/small/alarms/costa_del_lago/thresholds/pt-fit",
    ]
    for path in method_not_allowed_paths:
        response = client.get(path)
        assert response.status_code == 405
