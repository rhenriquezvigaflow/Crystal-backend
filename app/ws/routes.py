import asyncio

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.auth.services.lagoon_service import PERMISSION_VIEW
from app.security.rbac import ensure_websocket_permission

router = APIRouter()


async def _serve_scada_stream(websocket: WebSocket, lagoon_id: str) -> None:
    state = websocket.app.state.state_store
    ws_manager = websocket.app.state.ws_manager

    await websocket.accept()
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


@router.websocket("/ws/scada")
async def ws_scada(
    websocket: WebSocket,
    lagoon_id: str = Query(...),
    token: str | None = Query(None),
):
    ensure_websocket_permission(
        websocket=websocket,
        lagoon_id=lagoon_id,
        permission=PERMISSION_VIEW,
        token=token,
    )
    await _serve_scada_stream(websocket=websocket, lagoon_id=lagoon_id)


@router.websocket("/ws/scada/{lagoon_id}")
async def ws_scada_by_lagoon(
    websocket: WebSocket,
    lagoon_id: str,
    token: str | None = Query(None),
):
    ensure_websocket_permission(
        websocket=websocket,
        lagoon_id=lagoon_id,
        permission=PERMISSION_VIEW,
        token=token,
    )
    await _serve_scada_stream(websocket=websocket, lagoon_id=lagoon_id)


@router.websocket("/ws/crystal/{lagoon_id}")
async def ws_crystal_scada(
    websocket: WebSocket,
    lagoon_id: str,
    token: str | None = Query(None),
):
    ensure_websocket_permission(
        websocket=websocket,
        lagoon_id=lagoon_id,
        permission=PERMISSION_VIEW,
        token=token,
    )
    await _serve_scada_stream(websocket=websocket, lagoon_id=lagoon_id)


@router.websocket("/ws/small/{lagoon_id}")
async def ws_small_scada(
    websocket: WebSocket,
    lagoon_id: str,
    token: str | None = Query(None),
):
    ensure_websocket_permission(
        websocket=websocket,
        lagoon_id=lagoon_id,
        permission=PERMISSION_VIEW,
        token=token,
    )
    await _serve_scada_stream(websocket=websocket, lagoon_id=lagoon_id)
