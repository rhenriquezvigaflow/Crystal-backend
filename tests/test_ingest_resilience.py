from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.routers import ingest as ingest_router


def test_sync_failure_rolls_back_savepoint_and_keeps_session_usable():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)

    with Session(engine) as db:
        result = ingest_router._sync_collector_tags_and_alarms(
            db=db,
            lagoon_id="costa_del_lago",
            source_ts=datetime.now(timezone.utc),
            tags={"PT117_R_SCADA": 1.25},
        )

        assert result == (0, 0)
        assert db.execute(text("SELECT 1")).scalar_one() == 1


def test_collector_metadata_sync_is_throttled_per_lagoon(monkeypatch):
    ingest_router._reset_collector_sync_throttle()
    timestamps = iter((100.0, 110.0, 131.0, 132.0))

    monkeypatch.setattr(
        settings,
        "INGEST_COLLECTOR_SYNC_INTERVAL_SEC",
        30.0,
    )
    monkeypatch.setattr(
        ingest_router,
        "monotonic",
        lambda: next(timestamps),
    )

    assert ingest_router._should_sync_collector_metadata("costa_del_lago") is True
    assert ingest_router._should_sync_collector_metadata("costa_del_lago") is False
    assert ingest_router._should_sync_collector_metadata("costa_del_lago") is True
    assert ingest_router._should_sync_collector_metadata("ary") is True

    ingest_router._reset_collector_sync_throttle()


def test_ingest_transaction_uses_bounded_database_timeouts(monkeypatch):
    executed: list[tuple[object, dict[str, str]]] = []

    class FakeDb:
        def execute(self, statement, params):
            executed.append((statement, params))

    monkeypatch.setattr(settings, "INGEST_DB_STATEMENT_TIMEOUT_MS", 8000)
    monkeypatch.setattr(settings, "INGEST_DB_LOCK_TIMEOUT_MS", 1500)

    ingest_router._configure_ingest_transaction(db=FakeDb())

    assert executed[0][1] == {
        "statement_timeout": "8000ms",
        "lock_timeout": "1500ms",
    }


@pytest.mark.parametrize(
    "timeout_overrides",
    (
        {
            "INGEST_DB_LOCK_TIMEOUT_MS": 8000,
            "INGEST_DB_STATEMENT_TIMEOUT_MS": 8000,
        },
        {
            "INGEST_DB_STATEMENT_TIMEOUT_MS": 12000,
            "INGEST_REQUEST_TIMEOUT_SEC": 12,
        },
        {
            "DB_POOL_TIMEOUT_SEC": 12,
            "INGEST_REQUEST_TIMEOUT_SEC": 12,
        },
    ),
)
def test_ingest_timeout_order_is_validated(timeout_overrides):
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            DATABASE_URL="postgresql+psycopg2://test:test@localhost/test",
            COLLECTOR_API_KEY="collector-key-with-at-least-24-chars",
            JWT_SECRET_KEY="jwt-secret-key-with-at-least-32-characters",
            **timeout_overrides,
        )
