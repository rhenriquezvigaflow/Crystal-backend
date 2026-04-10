from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.jwt import get_current_user
from app.auth.services import lagoon_service
from app.db.session import get_db
from app.layout_config.schemas import (
    LayoutConfigResponse,
    LayoutDefinition,
    LayoutResponse,
    LagoonLayoutMappingResponse,
)
from app.layout_config.service import LagoonLayoutConfigService
from app.routers import scada_layouts as scada_layouts_router_module
from app.routers.scada_layouts import router as scada_layouts_router


class _DummyDB:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.flushes = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def flush(self) -> None:
        self.flushes += 1


class _Lagoon:
    def __init__(self, lagoon_id: str, scada_layout: str | None) -> None:
        self.id = lagoon_id
        self.scada_layout = scada_layout


def _sample_layout_response(layout_id: str = "layout2") -> LayoutResponse:
    return LayoutResponse(
        id=layout_id,
        name="Layout 2",
        json_definition=LayoutDefinition.model_validate(
            {
                "svg_component": "layout2",
                "elements": [
                    {
                        "id": "pressure_1",
                        "type": "kpi",
                        "position": {"top": "10%", "left": "10%"},
                    },
                    {
                        "id": "pump_1",
                        "type": "pump",
                        "svg_target": "BOMBA-FILTRACION",
                    },
                ],
            }
        ),
        updated_at=datetime(2026, 4, 9, tzinfo=timezone.utc),
    )


class _FakeLayoutConfigService:
    def __init__(self) -> None:
        self.get_layout_calls = 0
        self.get_mapping_calls = 0
        self.update_calls = 0

    def get_layout(self, *, db, layout_id: str) -> LayoutResponse:
        self.get_layout_calls += 1
        return _sample_layout_response(layout_id)

    def get_lagoon_mapping(self, *, db, lagoon) -> LagoonLayoutMappingResponse:
        self.get_mapping_calls += 1
        return LagoonLayoutMappingResponse(
            lagoon_id=lagoon.id,
            layout_id="layout2",
            mapping_json={
                "pressure_1": {"tag": "PT116_R_SCADA", "label": "Presion"}
            },
            collector_tags=["PT116_R_SCADA", "P006_STS_SCADA"],
            warnings=[],
            updated_at=datetime(2026, 4, 9, tzinfo=timezone.utc),
        )

    def update_layout_config(self, *, db, lagoon, layout_id: str, mapping_json):
        self.update_calls += 1
        return LayoutConfigResponse(
            lagoon_id=lagoon.id,
            layout=_sample_layout_response(layout_id),
            mapping=LagoonLayoutMappingResponse(
                lagoon_id=lagoon.id,
                layout_id=layout_id,
                mapping_json=mapping_json,
                warnings=[],
                updated_at=datetime(2026, 4, 9, tzinfo=timezone.utc),
            ),
        )


class _InMemoryLayoutConfigRepo:
    def __init__(self) -> None:
        self.layout_fetch_calls = 0
        self.mapping_fetch_calls = 0
        self.upsert_calls = 0
        self.layouts = {
            "layout1": {
                "id": "layout1",
                "name": "Layout 1",
                "json_definition": {
                    "svg_component": "layout1",
                    "elements": [
                        {"id": "pressure_1", "type": "kpi"},
                        {"id": "pump_1", "type": "pump"},
                    ],
                },
                "updated_at": datetime(2026, 4, 9, tzinfo=timezone.utc),
            }
        }
        self.mappings: dict[tuple[str, str], dict] = {}
        self.updated_at: dict[tuple[str, str], datetime] = {}
        self.collector_tags: dict[str, list[str]] = {}

    def get_layout(self, *, db, layout_id: str):
        self.layout_fetch_calls += 1
        raw = self.layouts.get(layout_id)
        if raw is None:
            return None

        class _LayoutRow:
            pass

        row = _LayoutRow()
        row.id = raw["id"]
        row.name = raw["name"]
        row.json_definition = raw["json_definition"]
        row.updated_at = raw["updated_at"]
        return row

    def get_mapping_for_layout(self, *, db, lagoon_id: str, layout_id: str):
        self.mapping_fetch_calls += 1
        key = (lagoon_id, layout_id)
        return dict(self.mappings.get(key, {})), self.updated_at.get(key)

    def upsert_mapping(self, *, db, lagoon_id: str, layout_id: str, mapping_json: dict):
        self.upsert_calls += 1
        key = (lagoon_id, layout_id)
        self.mappings[key] = dict(mapping_json)
        self.updated_at[key] = datetime.now(timezone.utc)

    def get_collector_tags(self, *, db, lagoon_id: str):
        return list(self.collector_tags.get(lagoon_id, []))


def _build_app(user_payload: dict) -> FastAPI:
    app = FastAPI()
    app.include_router(scada_layouts_router)

    dummy_db = _DummyDB()

    def _override_db():
        yield dummy_db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = lambda: user_payload
    return app


def test_get_layout_endpoint_returns_layout(monkeypatch):
    user = {"sub": "viewer-1", "email": "viewer@local.test", "roles": ["VisualCrystal"]}
    app = _build_app(user)
    fake_service = _FakeLayoutConfigService()
    monkeypatch.setattr(scada_layouts_router_module, "layout_config_service", fake_service)

    client = TestClient(app)
    response = client.get("/layouts/layout2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "layout2"
    assert payload["json_definition"]["svg_component"] == "layout2"
    assert len(payload["json_definition"]["elements"]) == 2
    assert fake_service.get_layout_calls == 1


def test_get_lagoon_mapping_endpoint_checks_access(monkeypatch):
    user = {"sub": "viewer-2", "email": "viewer2@local.test", "roles": ["VisualCrystal"]}
    app = _build_app(user)

    def _fake_ensure_lagoon_access(**kwargs):
        assert kwargs["permission"] == lagoon_service.PERMISSION_VIEW
        assert kwargs["lagoon_id"] == "lagoon-1"
        return _Lagoon("lagoon-1", "layout2")

    fake_service = _FakeLayoutConfigService()
    monkeypatch.setattr(scada_layouts_router_module, "ensure_lagoon_access", _fake_ensure_lagoon_access)
    monkeypatch.setattr(scada_layouts_router_module, "layout_config_service", fake_service)

    client = TestClient(app)
    response = client.get("/lagoons/lagoon-1/mapping")

    assert response.status_code == 200
    payload = response.json()
    assert payload["lagoon_id"] == "lagoon-1"
    assert payload["layout_id"] == "layout2"
    assert payload["mapping_json"]["pressure_1"]["tag"] == "PT116_R_SCADA"
    assert payload["collector_tags"] == ["PT116_R_SCADA", "P006_STS_SCADA"]
    assert fake_service.get_mapping_calls == 1


def test_put_lagoon_mapping_endpoint_updates_layout(monkeypatch):
    user = {"sub": "admin-1", "email": "admin@local.test", "roles": ["AdminCrystal"]}
    app = _build_app(user)

    def _fake_ensure_lagoon_access(**kwargs):
        assert kwargs["permission"] == lagoon_service.PERMISSION_EDIT
        assert kwargs["lagoon_id"] == "lagoon-1"
        return _Lagoon("lagoon-1", "layout1")

    fake_service = _FakeLayoutConfigService()
    monkeypatch.setattr(scada_layouts_router_module, "ensure_lagoon_access", _fake_ensure_lagoon_access)
    monkeypatch.setattr(scada_layouts_router_module, "layout_config_service", fake_service)

    client = TestClient(app)
    response = client.put(
        "/lagoons/lagoon-1/mapping",
        json={
            "layout_id": "layout2",
            "mapping_json": {
                "pump_1": {"tag": "P006_STS_SCADA", "label": "Bomba principal"},
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["layout_id"] == "layout2"
    assert payload["mapping_json"]["pump_1"]["tag"] == "P006_STS_SCADA"
    assert fake_service.update_calls == 1


def test_layout_config_service_uses_cache_for_layout_and_mapping():
    repo = _InMemoryLayoutConfigRepo()
    lagoon = _Lagoon("lagoon-cache-1", "layout1")
    repo.collector_tags[lagoon.id] = ["PT001"]
    now = [0.0]
    service = LagoonLayoutConfigService(repository=repo, ttl_sec=300, clock=lambda: now[0])

    first = service.get_layout_config(db=_DummyDB(), lagoon=lagoon)
    second = service.get_layout_config(db=_DummyDB(), lagoon=lagoon)

    assert first.layout.id == "layout1"
    assert first.mapping.layout_id == "layout1"
    assert first.mapping.collector_tags == ["PT001"]
    assert repo.layout_fetch_calls == 1
    assert repo.mapping_fetch_calls == 1
    assert second.layout.id == "layout1"

    now[0] = 301.0
    service.get_layout_config(db=_DummyDB(), lagoon=lagoon)
    assert repo.layout_fetch_calls == 2
    assert repo.mapping_fetch_calls == 2


def test_layout_config_service_refreshes_collector_tags_even_when_cached():
    repo = _InMemoryLayoutConfigRepo()
    lagoon = _Lagoon("lagoon-cache-collector", "layout1")
    repo.collector_tags[lagoon.id] = ["PT001"]
    service = LagoonLayoutConfigService(repository=repo, ttl_sec=300, clock=lambda: 0.0)

    first = service.get_layout_config(db=_DummyDB(), lagoon=lagoon)
    assert first.mapping.collector_tags == ["PT001"]

    repo.collector_tags[lagoon.id] = ["PT001", "FIT001"]
    second = service.get_layout_config(db=_DummyDB(), lagoon=lagoon)
    assert second.mapping.collector_tags == ["PT001", "FIT001"]


def test_layout_config_service_rejects_unknown_mapping_keys():
    repo = _InMemoryLayoutConfigRepo()
    lagoon = _Lagoon("lagoon-invalid-1", "layout1")
    service = LagoonLayoutConfigService(repository=repo, ttl_sec=300, clock=lambda: 0.0)

    try:
        service.update_layout_config(
            db=_DummyDB(),
            lagoon=lagoon,
            layout_id="layout1",
            mapping_json={"missing_element": {"tag": "PT001"}},
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 422
        assert "unknown layout elements" in str(exc.detail).lower()
    else:
        raise AssertionError("Expected HTTPException for invalid mapping")
