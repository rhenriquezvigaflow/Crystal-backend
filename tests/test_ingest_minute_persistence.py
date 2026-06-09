from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services import ingest_service
from app.services.scada_read_service import get_current
from app.state.store import RealtimeStateStore


class _FakeInsert:
    def __init__(self, model) -> None:
        self.model = model
        self.rows = []
        self.excluded = SimpleNamespace(
            state="state",
            value_num="value_num",
            value_bool="value_bool",
        )

    def values(self, rows):
        self.rows = list(rows)
        return self

    def on_conflict_do_update(self, **_kwargs):
        return self


class _FakeDb:
    def __init__(self) -> None:
        self.executed = []

    def execute(self, stmt):
        self.executed.append(stmt)


def test_ingest_persists_scada_minute_only_when_minute_rolls(monkeypatch):
    fake_db = _FakeDb()

    monkeypatch.setattr(ingest_service, "insert", lambda model: _FakeInsert(model))

    ingest_service.reset_runtime_state("test_minute_rollover")

    _, summary_1 = ingest_service.ingest(
        lagoon_id="kirah",
        ts=datetime(2026, 4, 16, 12, 0, 1, tzinfo=timezone.utc),
        tags={"FIT001": 1.0, "P001_ST_SCADA": 1},
        db=fake_db,
    )
    assert summary_1.minute_rows == 0
    assert fake_db.executed == []

    _, summary_2 = ingest_service.ingest(
        lagoon_id="kirah",
        ts=datetime(2026, 4, 16, 12, 0, 45, tzinfo=timezone.utc),
        tags={"FIT001": 2.5, "P001_ST_SCADA": 1},
        db=fake_db,
    )
    assert summary_2.minute_rows == 0
    assert fake_db.executed == []

    _, summary_3 = ingest_service.ingest(
        lagoon_id="kirah",
        ts=datetime(2026, 4, 16, 12, 1, 0, tzinfo=timezone.utc),
        tags={"FIT001": 3.0, "P001_ST_SCADA": 1},
        db=fake_db,
    )
    assert summary_3.minute_rows == 2
    assert summary_3.bucket_utc == datetime(2026, 4, 16, 12, 0, 0, tzinfo=timezone.utc)
    assert len(fake_db.executed) == 1

    persisted_rows = fake_db.executed[0].rows
    persisted_by_tag = {row["tag_id"]: row for row in persisted_rows}
    assert persisted_by_tag["FIT001"]["bucket"] == datetime(2026, 4, 16, 12, 0, 0, tzinfo=timezone.utc)
    assert persisted_by_tag["FIT001"]["value_num"] == 2.5


def test_ingest_persists_state_tag_float_value_in_state_column(monkeypatch):
    fake_db = _FakeDb()

    monkeypatch.setattr(ingest_service, "insert", lambda model: _FakeInsert(model))

    ingest_service.reset_runtime_state("test_filtracion_state_tag")

    ingest_service.ingest(
        lagoon_id="kirah",
        ts=datetime(2026, 4, 16, 12, 0, 1, tzinfo=timezone.utc),
        tags={"FILTRACION.ST": 10.0},
        db=fake_db,
    )

    _, summary = ingest_service.ingest(
        lagoon_id="kirah",
        ts=datetime(2026, 4, 16, 12, 1, 0, tzinfo=timezone.utc),
        tags={"FILTRACION.ST": "10"},
        db=fake_db,
    )

    assert summary.minute_rows == 1
    persisted_rows = fake_db.executed[0].rows
    assert persisted_rows == [
        {
            "lagoon_id": "kirah",
            "tag_id": "FILTRACION.ST",
            "bucket": datetime(2026, 4, 16, 12, 0, 0, tzinfo=timezone.utc),
            "state": 10,
            "value_num": None,
            "value_bool": None,
        }
    ]


def test_get_current_prefers_realtime_state_store():
    state_store = RealtimeStateStore()
    asyncio.run(
        state_store.update(
            lagoon_id="kirah",
            tags={"FIT001": 7.2},
            ts="2026-04-16T12:00:10+00:00",
        )
    )

    response = get_current(
        "kirah",
        db=SimpleNamespace(),
        state_store=state_store,
    )

    assert response is not None
    assert response["lagoon_id"] == "kirah"
    assert response["tags"]["FIT001"] == 7.2
