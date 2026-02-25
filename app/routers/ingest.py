import asyncio
import os
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional

from app.db.session import SessionLocal
from app.services.ingest_service import ingest
from app.security.api_key import verify_collector_key

router = APIRouter()
INGEST_TIMEOUT_SEC = float(os.getenv("INGEST_TIMEOUT_SEC", "125"))


class IngestPayload(BaseModel):
    lagoon_id: str
    timestamp: Optional[datetime] = None
    tags: dict


def _persist_ingest(lagoon_id: str, ts_dt: datetime, tags: dict):
    db = SessionLocal()
    try:
        pump_last_on_updates = ingest(
            lagoon_id=lagoon_id,
            ts=ts_dt,
            tags=tags,
            db=db,
        )
        db.commit()
        return pump_last_on_updates
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


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
        pump_last_on_updates = await asyncio.wait_for(
            asyncio.to_thread(
                _persist_ingest,
                lagoon_id,
                ts_dt,
                tags,
            ),
            timeout=INGEST_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError:
        print(
            f"[INGEST TIMEOUT] lagoon={lagoon_id} "
            f"timeout={INGEST_TIMEOUT_SEC}s"
        )
        raise HTTPException(
            status_code=504,
            detail="Ingest timeout",
        )
    except Exception as e:
        print("[INGEST DB ERROR]", e)
        raise

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
