from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Tuple
from threading import Lock

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.models.scada_minute import ScadaMinute
from app.models.scada_event import ScadaEvent
from app.core.logging import get_logger

logger = get_logger("ingest")

# ==========================================================
# Thread-safe state
# ==========================================================

_lock = Lock()

_minute_buffer: Dict[Tuple[str, datetime], Dict[str, list]] = {}
_last_bool_state: Dict[Tuple[str, str], bool] = {}
_open_event_id: Dict[Tuple[str, str], int] = {}

# ==========================================================
# Utils
# ==========================================================

def _to_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _bucket_minute(ts: datetime) -> datetime:
    ts = _to_utc(ts)
    return ts.replace(second=0, microsecond=0)

# ==========================================================
# Ingest principal
# ==========================================================

def ingest(
    lagoon_id: str,
    ts: datetime,
    tags: dict,
    db: Session,
):
    ts_utc = _to_utc(ts)
    bucket = _bucket_minute(ts_utc)

    with _lock:
        key = (lagoon_id, bucket)
        _minute_buffer.setdefault(key, {})

        # =========================
        # BUFFER + EVENTOS
        # =========================
        for tag_id, value in tags.items():
            _minute_buffer[key].setdefault(tag_id, []).append(value)

            if not isinstance(value, bool):
                continue

            prev = _last_bool_state.get((lagoon_id, tag_id))

            # OPEN
            if (prev in (False, None)) and value is True:
                ev = ScadaEvent(
                    lagoon_id=lagoon_id,
                    tag_id=tag_id,
                    tag_label=tag_id,
                    start_ts=ts_utc,
                )
                db.add(ev)
                db.flush()

                _open_event_id[(lagoon_id, tag_id)] = ev.id
                logger.info(f"EVENT OPEN lagoon={lagoon_id} tag={tag_id}")

            # CLOSE
            elif prev is True and value is False:
                ev_id = _open_event_id.pop((lagoon_id, tag_id), None)
                if ev_id:
                    db.query(ScadaEvent).filter(
                        ScadaEvent.id == ev_id
                    ).update({"end_ts": ts_utc})

                    logger.info(f"EVENT CLOSE lagoon={lagoon_id} tag={tag_id}")

            _last_bool_state[(lagoon_id, tag_id)] = value

        db.commit()

        # =========================
        # FLUSH MINUTOS CERRADOS
        # =========================
        flush_keys = [
            k for k in list(_minute_buffer.keys())
            if k[0] == lagoon_id and k[1] < bucket
        ]

        for fk in flush_keys:
            lagoon_id_fk, bucket = fk
            tag_dict = _minute_buffer.pop(fk, {})

            for tag_id, values in tag_dict.items():
                last_val = values[-1]

                value_num = (
                    float(last_val)
                    if isinstance(last_val, (int, float)) and not isinstance(last_val, bool)
                    else None
                )

                value_bool = last_val if isinstance(last_val, bool) else None

                stmt = insert(ScadaMinute).values(
                    lagoon_id=lagoon_id_fk,
                    tag_id=tag_id,
                    bucket=bucket,
                    value_num=value_num,
                    value_bool=value_bool,
                )

                stmt = stmt.on_conflict_do_update(
                    index_elements=["lagoon_id", "tag_id", "bucket"],
                    set_={
                        "value_num": stmt.excluded.value_num,
                        "value_bool": stmt.excluded.value_bool,
                        "updated_at": stmt.excluded.updated_at,
                    },
                )

                db.execute(stmt)

            logger.info(
                f"FLUSH lagoon={lagoon_id_fk} bucket={bucket.isoformat()}"
            )

        if flush_keys:
            db.commit()
