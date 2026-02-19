from __future__ import annotations

from datetime import datetime
from typing import Dict, Tuple, Any, List
from threading import Lock

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.models.scada_minute import ScadaMinute
from app.models.scada_event import ScadaEvent
from app.scada.value_codec import (
    is_state_or_bool_value,
    to_storage_fields,
)

_lock = Lock()

_minute_buffer: Dict[
    Tuple[str, datetime],
    Dict[str, List[Any]]
] = {}

_last_state: Dict[tuple[str, str], Any] = {}


def initialize_last_state(lagoon_id: str, states: Dict[str, Any]):
    for tag_id, value in states.items():
        _last_state[(lagoon_id, tag_id)] = value


def _bucket_minute(ts: datetime) -> datetime:
    return ts.replace(second=0, microsecond=0)


def ingest(
    lagoon_id: str,
    ts: datetime,
    tags: dict,
    db: Session,
):

    bucket = _bucket_minute(ts)

    detected_events: List[tuple[str, Any, Any]] = []
    flush_rows: List[tuple[str, datetime, str, Any]] = []

    with _lock:

        key = (lagoon_id, bucket)
        _minute_buffer.setdefault(key, {})

        for tag_id, value in tags.items():

            if not is_state_or_bool_value(value):
                continue

            state_key = (lagoon_id, tag_id)
            previous = _last_state.get(state_key)

            if previous is None:
                _last_state[state_key] = value
                continue

            if previous != value:
                detected_events.append((tag_id, previous, value))
                _last_state[state_key] = value

        for tag_id, value in tags.items():
            _minute_buffer[key].setdefault(tag_id, []).append(value)

        flush_keys = [
            k for k in list(_minute_buffer.keys())
            if k[0] == lagoon_id and k[1] < bucket
        ]

        for fk in flush_keys:
            lagoon_id_fk, bucket_fk = fk
            tag_dict = _minute_buffer.pop(fk, {})

            for tag_id, values in tag_dict.items():
                last_val = values[-1]
                flush_rows.append(
                    (lagoon_id_fk, bucket_fk, tag_id, last_val)
                )

    try:

        for tag_id, previous, value in detected_events:

            print(
                f"[EVENT DETECTED] {lagoon_id} {tag_id} "
                f"{previous} -> {value}"
            )

            open_event = (
                db.query(ScadaEvent)
                .filter(
                    ScadaEvent.lagoon_id == lagoon_id,
                    ScadaEvent.tag_id == tag_id,
                    ScadaEvent.end_ts.is_(None),
                )
                .order_by(ScadaEvent.start_ts.desc())
                .first()
            )

            if open_event:
                duration = int(
                    (ts - open_event.start_ts).total_seconds()
                )
                open_event.end_ts = ts
                open_event.duration_sec = duration

                print(
                    f"[EVENT CLOSED] {tag_id} "
                    f"duration={duration}s"
                )

            new_event = ScadaEvent(
                lagoon_id=lagoon_id,
                tag_id=tag_id,
                tag_label=tag_id,
                start_ts=ts,
                previous_state=int(previous),
                state=int(value),
                alert_type="STATE_CHANGE",
            )

            db.add(new_event)

            print(
                f"[EVENT INSERTED] "
                f"{lagoon_id} {tag_id}"
            )

        for lagoon_id_fk, bucket_fk, tag_id, last_val in flush_rows:

            state, value_num, value_bool = to_storage_fields(last_val)

            stmt = insert(ScadaMinute).values(
                lagoon_id=lagoon_id_fk,
                tag_id=tag_id,
                bucket=bucket_fk,
                state=state,
                value_num=value_num,
                value_bool=value_bool,
            )

            stmt = stmt.on_conflict_do_update(
                index_elements=["lagoon_id", "tag_id", "bucket"],
                set_={
                    "state": stmt.excluded.state,
                    "value_num": stmt.excluded.value_num,
                    "value_bool": stmt.excluded.value_bool,
                },
            )

            db.execute(stmt)

            print(
                f"[MINUTE UPSERT] "
                f"{lagoon_id_fk} {tag_id} {bucket_fk}"
            )

    except Exception:
        db.rollback()
        raise
