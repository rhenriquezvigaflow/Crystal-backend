import asyncio
import os
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional

from app.alarms.notifier import dispatch_notifications
from app.alarms.service import evaluate_alarms
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.services.ingest_service import ingest
from app.security.api_key import verify_collector_key

router = APIRouter()
logger = get_logger("api.ingest")
INGEST_TIMEOUT_SEC = float(os.getenv("INGEST_TIMEOUT_SEC", "125"))


class IngestPayload(BaseModel):
    lagoon_id: str
    timestamp: Optional[datetime] = None
    tags: dict


def _persist_ingest(lagoon_id: str, ts_dt: datetime, tags: dict):
    notification_jobs = []
    transition_count = 0

    db = SessionLocal()
    try:
        pump_last_on_updates = ingest(
            lagoon_id=lagoon_id,
            ts=ts_dt,
            tags=tags,
            db=db,
        )

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
                "[ERROR NOTIFICADOR ALARMAS] lagoon_id=%s",
                lagoon_id,
            )

    return pump_last_on_updates, transition_count


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

    try:
        pump_last_on_updates, alarm_transition_count = await asyncio.wait_for(
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
            "[INGEST TIMEOUT] lagoon_id=%s timeout_sec=%s",
            lagoon_id,
            INGEST_TIMEOUT_SEC,
        )
        raise HTTPException(
            status_code=504,
            detail="Ingest timeout",
        )
    except Exception:
        logger.exception(
            "[INGEST DB ERROR] lagoon_id=%s",
            lagoon_id,
        )
        raise

    if alarm_transition_count:
        logger.info(
            "[INGEST ALARMAS] lagoon_id=%s transiciones=%s",
            lagoon_id,
            alarm_transition_count,
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
