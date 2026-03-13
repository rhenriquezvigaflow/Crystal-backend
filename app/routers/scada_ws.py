from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from app.deps.realtime import get_ws_manager, get_state_store
from app.security.rbac import ALL_READ_ROLES, ensure_websocket_roles

router = APIRouter()

@router.websocket("/ws/scada/{lagoon_id}")
async def scada_ws(
    lagoon_id: str,
    ws: WebSocket,
    token: str | None = Query(None),
    manager=Depends(get_ws_manager),
    state=Depends(get_state_store),
):
    ensure_websocket_roles(
        websocket=ws,
        roles=ALL_READ_ROLES,
        token=token,
    )
    await ws.accept()
    await manager.connect(lagoon_id, ws)

    snapshot = state.get_snapshot(str(lagoon_id))
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
