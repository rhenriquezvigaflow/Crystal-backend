from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import asyncio

router = APIRouter()

@router.websocket("/ws/scada")
async def ws_scada(
    websocket: WebSocket,
    lagoon_id: str = Query(...),
):
    await websocket.accept()
    state = websocket.app.state.state_store
    ws_manager = websocket.app.state.ws_manager
    await ws_manager.connect(lagoon_id, websocket)
    try:
        snapshot = state.snapshot(lagoon_id)
        await websocket.send_json(snapshot)

        while True:
            await asyncio.sleep(3600)

    except WebSocketDisconnect:
        pass

    finally:
        await ws_manager.disconnect(lagoon_id, websocket)
