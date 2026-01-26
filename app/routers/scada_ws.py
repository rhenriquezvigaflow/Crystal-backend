from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.deps.realtime import get_ws_manager, get_state_store

router = APIRouter()

@router.websocket("/ws/scada/{lagoon_id}")
async def scada_ws(
    lagoon_id: str,
    ws: WebSocket,
    manager=Depends(get_ws_manager),
    state=Depends(get_state_store),
):
    await manager.connect(lagoon_id, ws)

    snapshot = state.get(str(lagoon_id)) if hasattr(state, "get") else None
    if snapshot:
        await ws.send_json({
            "type": "snapshot",
            "lagoon_id": str(lagoon_id),
            **snapshot,
        })

    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(lagoon_id, ws)
