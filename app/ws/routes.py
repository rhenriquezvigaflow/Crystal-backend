import asyncio
import os

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, WebSocketException, status
from starlette.websockets import WebSocketState

from app.auth.services.lagoon_service import PERMISSION_VIEW
from app.core.logging import get_logger
from app.security.rbac import ensure_websocket_permission

router = APIRouter()
logger = get_logger("ws.scada")


def _get_heartbeat_seconds() -> float:
    raw = os.getenv("WS_HEARTBEAT_SEC", "0")
    try:
        value = float(raw)
    except ValueError:
        value = 0.0
    return max(0.0, value)


WS_HEARTBEAT_SEC = _get_heartbeat_seconds()


def _client_label(websocket: WebSocket) -> str:
    client = websocket.client
    if client is None:
        return "unknown"
    return f"{client.host}:{client.port}"


async def _safe_close(
    websocket: WebSocket,
    code: int,
    reason: str,
) -> None:
    try:
        if websocket.application_state == WebSocketState.CONNECTING:
            await websocket.accept()
        await websocket.close(code=code, reason=reason)
    except RuntimeError:
        # Already closed/disconnected.
        return
    except Exception:
        logger.exception(
            "[WS CLOSE ERROR] client=%s code=%s reason=%s",
            _client_label(websocket),
            code,
            reason,
        )


async def _serve_scada_stream(
    websocket: WebSocket,
    lagoon_id: str,
    user_id: str,
) -> None:
    state = websocket.app.state.state_store
    ws_manager = websocket.app.state.ws_manager
    client = _client_label(websocket)
    close_code = status.WS_1000_NORMAL_CLOSURE
    close_reason = "Client disconnected"
    registered_in_manager = False
    phase = "init"

    logger.info(
        "[WS ACCEPT START] lagoon_id=%s user_id=%s client=%s",
        lagoon_id,
        user_id,
        client,
    )
    await websocket.accept()
    logger.info(
        "[WS ACCEPT DONE] lagoon_id=%s user_id=%s client=%s",
        lagoon_id,
        user_id,
        client,
    )

    try:
        phase = "snapshot_build"
        snapshot = state.snapshot(lagoon_id)
        logger.info(
            "[WS SEND START] lagoon_id=%s user_id=%s client=%s type=snapshot",
            lagoon_id,
            user_id,
            client,
        )
        await websocket.send_json(snapshot)
        logger.info(
            "[WS SEND OK] lagoon_id=%s user_id=%s client=%s type=snapshot",
            lagoon_id,
            user_id,
            client,
        )

        phase = "manager_connect"
        logger.info(
            "[WS REGISTER START] lagoon_id=%s user_id=%s client=%s",
            lagoon_id,
            user_id,
            client,
        )
        await ws_manager.connect(lagoon_id, websocket)
        registered_in_manager = True
        logger.info(
            "[WS REGISTER DONE] lagoon_id=%s user_id=%s client=%s",
            lagoon_id,
            user_id,
            client,
        )
        logger.info(
            "[WS STREAM START] lagoon_id=%s user_id=%s client=%s",
            lagoon_id,
            user_id,
            client,
        )

        while True:
            if WS_HEARTBEAT_SEC > 0:
                try:
                    phase = "receive_wait_heartbeat"
                    message = await asyncio.wait_for(
                        websocket.receive(),
                        timeout=WS_HEARTBEAT_SEC,
                    )
                except asyncio.TimeoutError:
                    phase = "send_ping"
                    logger.info(
                        "[WS SEND START] lagoon_id=%s user_id=%s client=%s type=ping",
                        lagoon_id,
                        user_id,
                        client,
                    )
                    await websocket.send_json({"type": "ping"})
                    logger.info(
                        "[WS SEND OK] lagoon_id=%s user_id=%s client=%s type=ping",
                        lagoon_id,
                        user_id,
                        client,
                    )
                    continue
            else:
                phase = "receive_wait"
                message = await websocket.receive()

            msg_type = str(message.get("type"))
            logger.info(
                "[WS RECEIVE] lagoon_id=%s user_id=%s client=%s type=%s",
                lagoon_id,
                user_id,
                client,
                msg_type,
            )
            if message.get("type") == "websocket.disconnect":
                close_code = int(
                    message.get("code") or status.WS_1000_NORMAL_CLOSURE
                )
                logger.warning(
                    "[WS RECEIVE DISCONNECT] lagoon_id=%s user_id=%s client=%s code=%s",
                    lagoon_id,
                    user_id,
                    client,
                    close_code,
                )
                break

    except WebSocketDisconnect as exc:
        close_code = exc.code or status.WS_1000_NORMAL_CLOSURE
        logger.warning(
            "[WS DISCONNECT EXC] lagoon_id=%s user_id=%s client=%s phase=%s code=%s",
            lagoon_id,
            user_id,
            client,
            phase,
            close_code,
        )
    except Exception:
        close_code = status.WS_1011_INTERNAL_ERROR
        close_reason = "Unhandled stream error"
        logger.exception(
            "[WS STREAM ERROR] lagoon_id=%s user_id=%s client=%s phase=%s",
            lagoon_id,
            user_id,
            client,
            phase,
        )
        await _safe_close(
            websocket=websocket,
            code=close_code,
            reason=close_reason,
        )

    finally:
        if registered_in_manager:
            logger.info(
                "[WS UNREGISTER START] lagoon_id=%s user_id=%s client=%s",
                lagoon_id,
                user_id,
                client,
            )
            await ws_manager.disconnect(lagoon_id, websocket)
            logger.info(
                "[WS UNREGISTER DONE] lagoon_id=%s user_id=%s client=%s",
                lagoon_id,
                user_id,
                client,
            )
        else:
            logger.info(
                "[WS UNREGISTER SKIP] lagoon_id=%s user_id=%s client=%s reason=not_registered",
                lagoon_id,
                user_id,
                client,
            )
        logger.info(
            "[WS CLOSED] lagoon_id=%s user_id=%s client=%s code=%s reason=%s",
            lagoon_id,
            user_id,
            client,
            close_code,
            close_reason,
        )


async def _handle_scada_websocket(
    websocket: WebSocket,
    lagoon_id: str,
    token: str | None,
) -> None:
    client = _client_label(websocket)
    origin = websocket.headers.get("origin", "-")
    forwarded_for = websocket.headers.get("x-forwarded-for", "-")
    forwarded_proto = websocket.headers.get("x-forwarded-proto", "-")
    has_token = bool(token) or bool(websocket.headers.get("authorization"))

    logger.info(
        "[WS HANDSHAKE] path=%s lagoon_id=%s client=%s origin=%s "
        "x_forwarded_for=%s x_forwarded_proto=%s has_token=%s",
        websocket.url.path,
        lagoon_id,
        client,
        origin,
        forwarded_for,
        forwarded_proto,
        has_token,
    )
    logger.info(
        "[WS AUTH START] lagoon_id=%s client=%s token_source=%s",
        lagoon_id,
        client,
        (
            "query"
            if token
            else "header"
            if websocket.headers.get("authorization")
            else "none"
        ),
    )

    try:
        user = ensure_websocket_permission(
            websocket=websocket,
            lagoon_id=lagoon_id,
            permission=PERMISSION_VIEW,
            token=token,
        )
    except WebSocketException as exc:
        reason = exc.reason or "Forbidden"
        logger.warning(
            "[WS REJECTED] lagoon_id=%s client=%s code=%s reason=%s",
            lagoon_id,
            client,
            exc.code,
            reason,
        )
        await _safe_close(
            websocket=websocket,
            code=exc.code,
            reason=reason,
        )
        return
    except Exception:
        logger.exception(
            "[WS AUTH ERROR] lagoon_id=%s client=%s",
            lagoon_id,
            client,
        )
        await _safe_close(
            websocket=websocket,
            code=status.WS_1011_INTERNAL_ERROR,
            reason="Authentication error",
        )
        return

    user_id = str(user.get("sub", "unknown"))
    logger.info(
        "[WS AUTHORIZED] lagoon_id=%s user_id=%s client=%s",
        lagoon_id,
        user_id,
        client,
    )
    await _serve_scada_stream(
        websocket=websocket,
        lagoon_id=lagoon_id,
        user_id=user_id,
    )


@router.websocket("/ws/scada")
async def ws_scada(
    websocket: WebSocket,
    lagoon_id: str = Query(...),
    token: str | None = Query(None),
):
    await _handle_scada_websocket(
        websocket=websocket,
        lagoon_id=lagoon_id,
        token=token,
    )


@router.websocket("/ws/scada/{lagoon_id}")
async def ws_scada_by_lagoon(
    websocket: WebSocket,
    lagoon_id: str,
    token: str | None = Query(None),
):
    await _handle_scada_websocket(
        websocket=websocket,
        lagoon_id=lagoon_id,
        token=token,
    )


@router.websocket("/ws/crystal/{lagoon_id}")
async def ws_crystal_scada(
    websocket: WebSocket,
    lagoon_id: str,
    token: str | None = Query(None),
):
    await _handle_scada_websocket(
        websocket=websocket,
        lagoon_id=lagoon_id,
        token=token,
    )


@router.websocket("/ws/small/{lagoon_id}")
async def ws_small_scada(
    websocket: WebSocket,
    lagoon_id: str,
    token: str | None = Query(None),
):
    await _handle_scada_websocket(
        websocket=websocket,
        lagoon_id=lagoon_id,
        token=token,
    )
