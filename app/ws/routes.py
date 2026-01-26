# app/ws/routes.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query

router = APIRouter()

def get_state_store():
    raise RuntimeError("StateStore dependency not wired")

def get_ws_manager():
    raise RuntimeError("WebSocketManager dependency not wired")


@router.websocket("/ws/scada")
async def ws_scada(
    websocket: WebSocket,
    lagoon_id: str = Query(...),
    state = Depends(get_state_store),
    ws = Depends(get_ws_manager),
):
    client = await ws.connect(websocket, lagoon_id)

    try:
        await websocket.send_json(state.snapshot(lagoon_id))

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await ws.disconnect(client)
