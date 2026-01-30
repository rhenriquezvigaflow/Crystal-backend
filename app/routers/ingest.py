# app/routers/ingest.py

from fastapi import APIRouter, Request
from pydantic import BaseModel
from datetime import datetime, timezone
from dateutil.parser import isoparse

from app.db.session import SessionLocal
from app.services.ingest_service import ingest

router = APIRouter()


class IngestPayload(BaseModel):
    lagoon_id: str
    ts: str | None = None
    tags: dict


@router.post("/ingest/scada")
async def ingest_scada(
    payload: IngestPayload,
    request: Request,
):
    # servicios compartidos
    state = request.app.state.state_store
    ws = request.app.state.ws_manager

    lagoon_id = payload.lagoon_id
    tags = payload.tags or {}

    # ===============================
    # 🕒 NORMALIZACIÓN DEFINITIVA DE TS
    # ===============================
    if payload.ts:
        # string ISO → datetime
        ts_dt = isoparse(payload.ts)
        if ts_dt.tzinfo is None:
            ts_dt = ts_dt.replace(tzinfo=timezone.utc)
    else:
        ts_dt = datetime.now(timezone.utc)

    # string solo para WS / state
    ts_iso = ts_dt.isoformat()

    # ===============================
    # 1️⃣ actualizar estado en memoria
    # ===============================
    await state.update(lagoon_id, tags, ts_iso)

    # ===============================
    # 2️⃣ persistir en base de datos
    # ===============================
    db = SessionLocal()
    try:
        ingest(
            lagoon_id=lagoon_id,
            ts=ts_dt,      # ✅ datetime con tzinfo
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

    # ===============================
    # 3️⃣ broadcast websocket
    # ===============================
    await ws.broadcast(
        lagoon_id,
        await state.tick_payload(lagoon_id),
    )

    return {"ok": True}
