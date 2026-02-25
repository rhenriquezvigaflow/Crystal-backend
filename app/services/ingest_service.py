from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Tuple, Any, List
from threading import Lock

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from datetime import datetime, timezone

from app.models.scada_minute import ScadaMinute
from app.models.scada_event import ScadaEvent
from app.scada.value_codec import (
    is_state_or_bool_value,
    to_storage_fields,
)

# =========================================================
# GLOBAL RUNTIME STATE
# =========================================================

_lock = Lock()

_minute_buffer: Dict[
    Tuple[str, datetime],
    Dict[str, List[Any]]
] = {}

_last_state: Dict[tuple[str, str], Any] = {}

_runtime_metrics = {
    "last_ingest_utc": None,
    "last_lagoon": None,
    "last_minute_rows": 0,
    "last_event_count": 0,
}


# =========================================================
# PUBLIC HELPERS
# =========================================================

def initialize_last_state(lagoon_id: str, states: Dict[str, Any]):
    for tag_id, value in states.items():
        _last_state[(lagoon_id, tag_id)] = value


def get_runtime_metrics():
    return _runtime_metrics.copy()


def _bucket_minute(ts: datetime) -> datetime:
    return ts.replace(second=0, microsecond=0)


def reset_runtime_state(
    reason: str = "manual",
    lock_timeout_sec: float = 1.0,
) -> bool:
    acquired = _lock.acquire(timeout=lock_timeout_sec)
    if not acquired:
        print(f"[INGEST RESET SKIPPED] reason={reason} lock busy")
        return False

    try:
        minute_keys = len(_minute_buffer)
        state_keys = len(_last_state)

        _minute_buffer.clear()
        _last_state.clear()

        print(
            f"[INGEST RESET] reason={reason} "
            f"cleared minute_buffer={minute_keys} "
            f"last_state={state_keys}"
        )
        return True

    finally:
        _lock.release()


def ingest(
    lagoon_id: str,
    ts: datetime,
    tags: dict,
    db: Session,
):

    bucket = _bucket_minute(ts)

    detected_events: List[tuple[str, Any, Any]] = []
    flush_rows: List[dict] = []


    with _lock:

        key = (lagoon_id, bucket)
        _minute_buffer.setdefault(key, {})

        # Detect state changes
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

                state, value_num, value_bool = to_storage_fields(last_val)

                flush_rows.append({
                    "lagoon_id": lagoon_id_fk,
                    "tag_id": tag_id,
                    "bucket": bucket_fk,
                    "state": state,
                    "value_num": value_num,
                    "value_bool": value_bool,
                })



    try:

        for tag_id, previous, value in detected_events:

            print(
                f"[EVENT DETECTED] {lagoon_id} "
                f"{tag_id} {previous} -> {value}"
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

        if flush_rows:

            stmt = insert(ScadaMinute).values(flush_rows)

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
                f"[BATCH MINUTE UPSERT] "
                f"utc={datetime.now(timezone.utc).isoformat()} "
                f"lagoon={lagoon_id} "
                f"bucket_utc={bucket.isoformat()} "
                f"rows={len(flush_rows)} "
                f"events={len(detected_events)}"
            )

        # -------------------------
        _runtime_metrics["last_ingest_utc"] = datetime.now(timezone.utc)
        _runtime_metrics["last_lagoon"] = lagoon_id
        _runtime_metrics["last_minute_rows"] = len(flush_rows)
        _runtime_metrics["last_event_count"] = len(detected_events)

        db.commit()

    except Exception:
        db.rollback()
        raise