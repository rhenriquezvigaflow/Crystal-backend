# app/ws/routes.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

router = APIRouter()


@router.websocket("/ws/scada")
async def ws_scada(
    websocket: WebSocket,
    lagoon_id: str = Query(...),
):
    # 1️⃣ aceptar conexión (OBLIGATORIO antes de enviar)
    await websocket.accept()

    # 2️⃣ obtener singletons desde app.state
    state = websocket.app.state.state_store
    ws_manager = websocket.app.state.ws_manager

    # 3️⃣ registrar conexión
    await ws_manager.connect(lagoon_id, websocket)

    try:
        # 4️⃣ enviar snapshot inicial (YA ES SEGURO)
        snapshot = state.snapshot(lagoon_id)
        await websocket.send_json(snapshot)

        # 5️⃣ loop pasivo (cliente no envía nada)
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass

    finally:
        await ws_manager.disconnect(lagoon_id, websocket)
