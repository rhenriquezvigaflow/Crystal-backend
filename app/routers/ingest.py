from fastapi import APIRouter, Request
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional

from app.db.session import SessionLocal
from app.services.ingest_service import ingest

router = APIRouter()


class IngestPayload(BaseModel):
    lagoon_id: str
    timestamp: Optional[datetime] = None
    tags: dict


@router.post("/ingest/scada")
async def ingest_scada(
    payload: IngestPayload,
    request: Request,
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

    # ===== DB + EVENT DETECTION =====
    db = SessionLocal()
    try:
        pump_last_on_updates = ingest(
            lagoon_id=lagoon_id,
            ts=ts_dt,
            tags=tags,
            db=db,
        )
        db.commit()
    except Exception as e:
        db.rollback()
        print("[INGEST DB ERROR]", e)
        raise
    finally:
        db.close()

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
