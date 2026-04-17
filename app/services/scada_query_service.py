from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.scada.history.repo import get_history_rows
from app.services.scada_read_service import get_current
from app.state.store import RealtimeStateStore

Resolution = Literal["hourly", "daily", "weekly"]


def get_realtime_payload(
    *,
    db: Session,
    lagoon_id: str,
    state_store: RealtimeStateStore | None = None,
) -> dict[str, Any] | None:
    return get_current(lagoon_id, db, state_store=state_store)


def get_history_payload(
    *,
    db: Session,
    lagoon_id: str,
    start_date: datetime,
    end_date: datetime,
    resolution: Resolution,
    tags: list[str] | None,
) -> dict[str, Any]:
    data = get_history_rows(
        db=db,
        lagoon_id=lagoon_id,
        start_date=start_date,
        end_date=end_date,
        resolution=resolution,
        tags=tags,
    )

    series_map: dict[str, list[dict[str, Any]]] = {}
    for row in data["rows"]:
        tag = row["tag_id"]
        series_map.setdefault(tag, []).append(
            {
                "timestamp": row["bucket"],
                "value": (
                    float(row["avg_val"])
                    if row["avg_val"] is not None
                    else None
                ),
            }
        )

    return {
        "lagoon_id": lagoon_id,
        "resolution": data["resolution"],
        "source": data["source"],
        "series": [
            {"tag": tag, "points": points}
            for tag, points in series_map.items()
        ],
    }


def get_kpis_payload(
    *,
    db: Session,
    lagoon_id: str,
    state_store: RealtimeStateStore | None,
) -> dict[str, Any] | None:
    realtime = get_current(lagoon_id, db, state_store=state_store)
    snapshot = state_store.snapshot(lagoon_id) if state_store is not None else {}

    if not realtime and not snapshot:
        return None

    tags = realtime.get("tags", {}) if isinstance(realtime, dict) else {}
    pump_last_on = (
        snapshot.get("pump_last_on", {})
        if isinstance(snapshot, dict)
        else {}
    )

    return {
        "lagoon_id": lagoon_id,
        "ts": (
            realtime.get("ts")
            if isinstance(realtime, dict)
            else snapshot.get("ts")
        ),
        "plc_status": snapshot.get("plc_status"),
        "local_time": snapshot.get("local_time"),
        "timezone": snapshot.get("timezone"),
        "tags_count": len(tags),
        "pump_events_count": len(pump_last_on),
        "pump_last_on": pump_last_on,
    }
