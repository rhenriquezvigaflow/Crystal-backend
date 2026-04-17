from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.scada_event import ScadaEvent
from app.models.scada_minute import ScadaMinute
from app.scada.value_codec import is_state_or_bool_value, to_storage_fields

_lock = Lock()

_last_state: dict[tuple[str, str], Any] = {}
_minute_buffers: dict[str, "_LagoonMinuteBuffer"] = {}

_runtime_metrics = {
    "last_ingest_utc": None,
    "last_lagoon": None,
    "last_minute_rows": 0,
    "last_event_count": 0,
}

logger = get_logger("services.ingest")


@dataclass(slots=True)
class ScadaEventWrite:
    action: str
    lagoon_id: str
    tag_id: str
    previous_state: int | None
    state: int | None
    happened_at: datetime
    duration_sec: int | None = None


@dataclass(slots=True)
class IngestWriteSummary:
    lagoon_id: str
    bucket_utc: datetime | None
    minute_rows: int
    detected_event_count: int
    event_writes: list[ScadaEventWrite]


@dataclass(slots=True)
class _LagoonMinuteBuffer:
    bucket_utc: datetime
    tags: dict[str, Any]


def initialize_last_state(lagoon_id: str, states: dict[str, Any]) -> None:
    for tag_id, value in states.items():
        _last_state[(lagoon_id, tag_id)] = value


def get_runtime_metrics() -> dict[str, Any]:
    return _runtime_metrics.copy()


def log_persisted_ingest(summary: IngestWriteSummary) -> None:
    if summary.minute_rows == 0 and summary.detected_event_count == 0:
        return

    if summary.minute_rows > 0 and summary.bucket_utc is not None:
        logger.info(
            "[INGEST DB] lagoon=%s bucket=%s rows=%s events=%s",
            summary.lagoon_id,
            summary.bucket_utc.isoformat(),
            summary.minute_rows,
            summary.detected_event_count,
        )

    for event in summary.event_writes:
        if event.action == "CLOSE":
            logger.info(
                "[SCADA EVENT CLOSE] lagoon=%s tag=%s previous=%s current=%s at=%s duration_sec=%s",
                event.lagoon_id,
                event.tag_id,
                event.previous_state,
                event.state,
                event.happened_at.isoformat(),
                event.duration_sec,
            )
            continue

        logger.info(
            "[SCADA EVENT OPEN] lagoon=%s tag=%s previous=%s current=%s at=%s",
            event.lagoon_id,
            event.tag_id,
            event.previous_state,
            event.state,
            event.happened_at.isoformat(),
        )


def _bucket_minute(ts: datetime) -> datetime:
    return ts.replace(second=0, microsecond=0)


def _to_running_state(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value > 0
    return False


def reset_runtime_state(
    reason: str = "manual",
    lock_timeout_sec: float = 1.0,
) -> bool:
    acquired = _lock.acquire(timeout=lock_timeout_sec)
    if not acquired:
        logger.warning(
            "[INGEST RESET SKIPPED] reason=%s lock=busy",
            reason,
        )
        return False

    try:
        state_keys = len(_last_state)
        minute_buffers = len(_minute_buffers)
        _last_state.clear()
        _minute_buffers.clear()
        logger.info(
            "[INGEST RESET] reason=%s cleared_last_state=%s cleared_minute_buffers=%s",
            reason,
            state_keys,
            minute_buffers,
        )
        return True
    finally:
        _lock.release()


def ingest(
    lagoon_id: str,
    ts: datetime,
    tags: dict,
    db: Session,
) -> tuple[dict[str, str], IngestWriteSummary]:
    bucket = _bucket_minute(ts)
    detected_events: list[tuple[str, Any, Any]] = []
    pump_last_on_updates: dict[str, str] = {}
    event_writes: list[ScadaEventWrite] = []
    minute_bucket_to_persist: datetime | None = None
    minute_tags_to_persist: dict[str, Any] = {}

    with _lock:
        for tag_id, value in tags.items():
            if not is_state_or_bool_value(value):
                continue

            state_key = (lagoon_id, tag_id)
            previous = _last_state.get(state_key)

            if previous is None:
                _last_state[state_key] = value
                continue

            if previous == value:
                continue

            detected_events.append((tag_id, previous, value))
            _last_state[state_key] = value

            if not _to_running_state(previous) and _to_running_state(value):
                pump_last_on_updates[tag_id] = ts.isoformat()

        current_buffer = _minute_buffers.get(lagoon_id)
        incoming_tags = dict(tags)
        if current_buffer is None:
            _minute_buffers[lagoon_id] = _LagoonMinuteBuffer(
                bucket_utc=bucket,
                tags=incoming_tags,
            )
        elif bucket == current_buffer.bucket_utc:
            current_buffer.tags.update(incoming_tags)
        elif bucket > current_buffer.bucket_utc:
            minute_bucket_to_persist = current_buffer.bucket_utc
            minute_tags_to_persist = dict(current_buffer.tags)
            _minute_buffers[lagoon_id] = _LagoonMinuteBuffer(
                bucket_utc=bucket,
                tags=incoming_tags,
            )
        else:
            logger.warning(
                "[INGEST OUT OF ORDER] lagoon=%s incoming_bucket=%s buffered_bucket=%s",
                lagoon_id,
                bucket.isoformat(),
                current_buffer.bucket_utc.isoformat(),
            )

    upsert_rows: list[dict[str, Any]] = []
    for tag_id, value in minute_tags_to_persist.items():
        state, value_num, value_bool = to_storage_fields(value)
        upsert_rows.append(
            {
                "lagoon_id": lagoon_id,
                "tag_id": tag_id,
                "bucket": minute_bucket_to_persist,
                "state": state,
                "value_num": value_num,
                "value_bool": value_bool,
            }
        )

    for tag_id, previous, value in detected_events:
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
            duration = int((ts - open_event.start_ts).total_seconds())
            open_event.end_ts = ts
            open_event.duration_sec = duration
            event_writes.append(
                ScadaEventWrite(
                    action="CLOSE",
                    lagoon_id=lagoon_id,
                    tag_id=tag_id,
                    previous_state=int(previous),
                    state=int(value),
                    happened_at=ts,
                    duration_sec=duration,
                )
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
        event_writes.append(
            ScadaEventWrite(
                action="OPEN",
                lagoon_id=lagoon_id,
                tag_id=tag_id,
                previous_state=int(previous),
                state=int(value),
                happened_at=ts,
            )
        )

    if upsert_rows:
        stmt = insert(ScadaMinute).values(upsert_rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["lagoon_id", "tag_id", "bucket"],
            set_={
                "state": stmt.excluded.state,
                "value_num": stmt.excluded.value_num,
                "value_bool": stmt.excluded.value_bool,
                "updated_at": datetime.now(timezone.utc),
            },
        )

        db.execute(stmt)

    _runtime_metrics["last_ingest_utc"] = datetime.now(timezone.utc)
    _runtime_metrics["last_lagoon"] = lagoon_id
    _runtime_metrics["last_minute_rows"] = len(upsert_rows)
    _runtime_metrics["last_event_count"] = len(detected_events)

    return (
        pump_last_on_updates,
        IngestWriteSummary(
            lagoon_id=lagoon_id,
            bucket_utc=minute_bucket_to_persist,
            minute_rows=len(upsert_rows),
            detected_event_count=len(detected_events),
            event_writes=event_writes,
        ),
    )
