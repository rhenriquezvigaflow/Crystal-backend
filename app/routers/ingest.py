from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas.ingest import CollectorPayload
from app.db.session import get_db
from app.services.ingest_service import ingest as ingest_db

from app.deps.realtime import get_state_store, get_ws_manager
from app.security.api_key import verify_collector_key


router = APIRouter()


@router.post("/ingest/scada")
async def ingest_scada(
    payload: CollectorPayload,
    db: Session = Depends(get_db),
    state = Depends(get_state_store),
    ws = Depends(get_ws_manager),
    _ = Depends(verify_collector_key),  
):
    """
    Endpoint de ingest SCADA.
    - Recibe datos normalizados del collector
    - Persiste minuto + eventos
    - Actualiza estado en memoria
    - Emite tick por WebSocket
    """

    lagoon_id = payload.lagoon_id
    ts = payload.timestamp
    tags = payload.tags

    # Persistencia (DB)
    ingest_db(
        lagoon_id=lagoon_id,
        ts=ts,
        tags=tags,
        db=db,
    )

    # Estado en memoria (REALTIME)
    state.update(
        str(lagoon_id),
        ts.isoformat(),
        tags,
    )

    # WebSocket
    await ws.broadcast(
        str(lagoon_id),
        {
            "type": "tick",
            "lagoon_id": str(lagoon_id),
            "ts": ts.isoformat().replace("+00:00", "Z"),
            "tags": tags,
        },
    )

    return {"status": "ok"}
