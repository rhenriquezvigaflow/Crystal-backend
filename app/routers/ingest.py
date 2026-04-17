import asyncio
import os
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB

from app.alarms.notifier import dispatch_notifications
from app.alarms.service import evaluate_alarms, log_persisted_alarm_transitions
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.services.ingest_service import ingest, log_persisted_ingest
from app.security.api_key import verify_collector_key

router = APIRouter()
logger = get_logger("api.ingest")
INGEST_TIMEOUT_SEC = float(os.getenv("INGEST_TIMEOUT_SEC", "125"))
SYNC_COLLECTOR_TAGS_SQL = text(
    """
    SELECT CASE
        WHEN to_regproc('public.sp_sync_collector_tags_and_alarms') IS NULL
            THEN NULL
        ELSE public.sp_sync_collector_tags_and_alarms(
            :lagoon_id,
            :source_ts,
            :tags_payload
        )
    END AS sync_result
    """
).bindparams(bindparam("tags_payload", type_=JSONB))


class IngestPayload(BaseModel):
    lagoon_id: str
    timestamp: Optional[datetime] = None
    tags: dict


def _sync_collector_tags_and_alarms(
    *,
    db,
    lagoon_id: str,
    source_ts: datetime,
    tags: dict,
) -> tuple[int, int]:
    if not tags:
        return 0, 0

    try:
        result = db.execute(
            SYNC_COLLECTOR_TAGS_SQL,
            {
                "lagoon_id": lagoon_id,
                "source_ts": source_ts,
                "tags_payload": tags,
            },
        ).scalar_one_or_none()

        if isinstance(result, dict):
            return (
                int(result.get("registered_tags") or 0),
                int(result.get("new_alarm_definitions") or 0),
            )
    except Exception:
        logger.exception(
            "[INGEST SYNC ERROR] lagoon=%s",
            lagoon_id,
        )
    return 0, 0


def _persist_ingest(lagoon_id: str, ts_dt: datetime, tags: dict):
    notification_jobs = []
    transition_count = 0
    minute_row_count = 0
    event_count = 0

    db = SessionLocal()
    try:
        sync_registered_tags, sync_new_alarm_definitions = _sync_collector_tags_and_alarms(
            db=db,
            lagoon_id=lagoon_id,
            source_ts=ts_dt,
            tags=tags,
        )

        pump_last_on_updates, ingest_summary = ingest(
            lagoon_id=lagoon_id,
            ts=ts_dt,
            tags=tags,
            db=db,
        )
        minute_row_count = ingest_summary.minute_rows
        event_count = ingest_summary.detected_event_count

        transitions, notification_jobs = evaluate_alarms(
            payload={
                "lagoon_id": lagoon_id,
                "timestamp": ts_dt,
                "tags": tags,
            },
            db=db,
        )
        transition_count = len(transitions)

        db.commit()
        if sync_registered_tags or sync_new_alarm_definitions:
            logger.info(
                "[INGEST SYNC] lagoon=%s tags=%s alarms=%s",
                lagoon_id,
                sync_registered_tags,
                sync_new_alarm_definitions,
            )
        log_persisted_ingest(ingest_summary)
        log_persisted_alarm_transitions(transitions)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    if notification_jobs:
        try:
            dispatch_notifications(notification_jobs)
        except Exception:
            logger.exception(
                "[NOTIFY ERROR] lagoon=%s reason=dispatch_failed",
                lagoon_id,
            )

    return pump_last_on_updates, transition_count, minute_row_count, event_count


@router.post("/ingest/scada")
async def ingest_scada(
    payload: IngestPayload,
    request: Request,
    _: None = Depends(verify_collector_key),
):
    state = request.app.state.state_store
    ws = request.app.state.ws_manager

    lagoon_id = payload.lagoon_id
    tags = payload.tags or {}

    # ===== UTC timestamp =====
    if payload.timestamp:
        ts_dt = payload.timestamp
        if ts_dt.tzinfo is None:
            ts_dt = ts_dt.replace(tzinfo=timezone.utc)
    else:
        ts_dt = datetime.now(timezone.utc)

    ts_iso = ts_dt.isoformat()
    client_ip = request.client.host if request.client else "-"

    try:
        (
            pump_last_on_updates,
            alarm_transition_count,
            minute_row_count,
            scada_event_count,
        ) = await asyncio.wait_for(
            asyncio.to_thread(
                _persist_ingest,
                lagoon_id,
                ts_dt,
                tags,
            ),
            timeout=INGEST_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "[INGEST TIMEOUT] lagoon=%s ip=%s timeout_sec=%s",
            lagoon_id,
            client_ip,
            INGEST_TIMEOUT_SEC,
        )
        raise HTTPException(
            status_code=504,
            detail="Ingest timeout",
        )
    except Exception:
        logger.exception(
            "[INGEST ERROR] lagoon=%s ip=%s",
            lagoon_id,
            client_ip,
        )
        raise

    if alarm_transition_count:
        logger.info(
            "[INGEST ALARMS] lagoon=%s count=%s",
            lagoon_id,
            alarm_transition_count,
        )

    ingest_log = logger.info
    if (
        minute_row_count == 0
        and scada_event_count == 0
        and alarm_transition_count == 0
    ):
        ingest_log = logger.debug

    ingest_log(
        "[INGEST OK] lagoon=%s ip=%s rows=%s events=%s alarms=%s at=%s",
        lagoon_id,
        client_ip,
        minute_row_count,
        scada_event_count,
        alarm_transition_count,
        ts_iso,
    )

    # ===== REALTIME =====
    await state.update(
        lagoon_id=lagoon_id,
        tags=tags,
        ts=ts_iso,
        pump_last_on_updates=pump_last_on_updates,
    )

    # ===== WS =====
    await ws.broadcast(
        lagoon_id,
        await state.tick_payload(lagoon_id),
    )

    return {"ok": True}
