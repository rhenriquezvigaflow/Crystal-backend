import asyncio
import os
from urllib.parse import urlsplit

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException, status
from starlette.websockets import WebSocketState

from app.auth.services.lagoon_service import PERMISSION_VIEW, get_lagoon_by_id
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.security.rbac import (
    describe_websocket_token_source,
    ensure_websocket_permission,
)

router = APIRouter(tags=["websocket"])
logger = get_logger("ws.scada")
WS_SUBPROTOCOL = "crystal-scada.v1"


def _get_heartbeat_seconds() -> float:
    raw = os.getenv("WS_HEARTBEAT_SEC", "15")
    try:
        value = float(raw)
    except ValueError:
        value = 15.0
    # Keepalive obligatorio: minimo 1s.
    return max(1.0, value)


WS_HEARTBEAT_SEC = _get_heartbeat_seconds()


def _client_label(websocket: WebSocket) -> str:
    client = websocket.client
    if client is None:
        return "unknown"
    return f"{client.host}:{client.port}"


def _resolve_accept_subprotocol(websocket: WebSocket) -> str | None:
    header_value = websocket.headers.get("sec-websocket-protocol")
    if not header_value:
        return None

    protocols = {
        token.strip()
        for token in header_value.split(",")
        if token and token.strip()
    }
    if WS_SUBPROTOCOL in protocols:
        return WS_SUBPROTOCOL
    return None


def _is_origin_allowed(origin: str | None) -> bool:
    if not origin:
        return True

    normalized_origin = origin.strip().rstrip("/")
    allowed_origins = settings.effective_ws_allowed_origins
    if not allowed_origins:
        return True
    if "*" in allowed_origins:
        return True
    return normalized_origin in allowed_origins


def _extract_hostname(raw_value: str | None) -> str | None:
    if not raw_value:
        return None

    candidate = raw_value.strip().rstrip("/")
    if not candidate:
        return None

    parsed = (
        urlsplit(candidate)
        if "://" in candidate
        else urlsplit(f"//{candidate}")
    )
    if not parsed.hostname:
        return None
    return parsed.hostname.lower()


def _same_host_origin_allowed(
    websocket: WebSocket,
    origin: str | None,
) -> bool:
    origin_host = _extract_hostname(origin)
    if not origin_host:
        return False

    request_hosts = {
        _extract_hostname(websocket.headers.get("x-forwarded-host")),
        _extract_hostname(websocket.headers.get("host")),
        _extract_hostname(str(websocket.url)),
        _extract_hostname(websocket.url.hostname),
    }

    request_hosts.discard(None)
    return origin_host in request_hosts


def _is_origin_allowed_for_websocket(
    websocket: WebSocket,
    origin: str | None,
) -> bool:
    if _same_host_origin_allowed(websocket, origin):
        return True
    return _is_origin_allowed(origin)


def _is_valid_lagoon_id(lagoon_id: str) -> bool:
    db = SessionLocal()
    try:
        return get_lagoon_by_id(db=db, lagoon_id=lagoon_id) is not None
    finally:
        db.close()


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
    accept_subprotocol: str | None = None,
) -> None:
    state = websocket.app.state.state_store
    ws_manager = websocket.app.state.ws_manager
    client = _client_label(websocket)
    close_code = status.WS_1000_NORMAL_CLOSURE
    close_reason = "Client disconnected"
    registered_in_manager = False
    phase = "init"

    logger.debug(
        "[WS ACCEPT START] lagoon_id=%s user_id=%s client=%s",
        lagoon_id,
        user_id,
        client,
    )
    await websocket.accept(subprotocol=accept_subprotocol)
    logger.debug(
        "[WS ACCEPT DONE] lagoon_id=%s user_id=%s client=%s",
        lagoon_id,
        user_id,
        client,
    )

    try:
        phase = "snapshot_build"
        snapshot = state.snapshot(lagoon_id)
        logger.debug(
            "[WS SEND START] lagoon_id=%s user_id=%s client=%s type=snapshot",
            lagoon_id,
            user_id,
            client,
        )
        await websocket.send_json(snapshot)
        logger.debug(
            "[WS SEND OK] lagoon_id=%s user_id=%s client=%s type=snapshot",
            lagoon_id,
            user_id,
            client,
        )

        phase = "manager_connect"
        logger.debug(
            "[WS REGISTER START] lagoon_id=%s user_id=%s client=%s",
            lagoon_id,
            user_id,
            client,
        )
        await ws_manager.connect(lagoon_id, websocket)
        registered_in_manager = True
        logger.debug(
            "[WS REGISTER DONE] lagoon_id=%s user_id=%s client=%s",
            lagoon_id,
            user_id,
            client,
        )
        logger.debug(
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
                    logger.debug(
                        "[WS SEND START] lagoon_id=%s user_id=%s client=%s type=ping",
                        lagoon_id,
                        user_id,
                        client,
                    )
                    await websocket.send_json({"type": "ping"})
                    logger.debug(
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
            logger.debug(
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
            logger.debug(
                "[WS UNREGISTER START] lagoon_id=%s user_id=%s client=%s",
                lagoon_id,
                user_id,
                client,
            )
            await ws_manager.disconnect(lagoon_id, websocket)
            logger.debug(
                "[WS UNREGISTER DONE] lagoon_id=%s user_id=%s client=%s",
                lagoon_id,
                user_id,
                client,
            )
        else:
            logger.debug(
                "[WS UNREGISTER SKIP] lagoon_id=%s user_id=%s client=%s reason=not_registered",
                lagoon_id,
                user_id,
                client,
            )
        logger.debug(
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
) -> None:
    client = _client_label(websocket)
    origin = websocket.headers.get("origin", "-")
    forwarded_for = websocket.headers.get("x-forwarded-for", "-")
    forwarded_proto = websocket.headers.get("x-forwarded-proto", "-")
    has_token = describe_websocket_token_source(websocket) != "none"
    accept_subprotocol = _resolve_accept_subprotocol(websocket)

    logger.debug(
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
    logger.debug(
        "[WS AUTH START] lagoon_id=%s client=%s token_source=%s",
        lagoon_id,
        client,
        describe_websocket_token_source(websocket),
    )

    if not _is_origin_allowed_for_websocket(
        websocket,
        None if origin == "-" else origin,
    ):
        logger.warning(
            "[WS REJECTED] lagoon_id=%s client=%s code=%s reason=Origin not allowed origin=%s",
            lagoon_id,
            client,
            status.WS_1008_POLICY_VIOLATION,
            origin,
        )
        await _safe_close(
            websocket=websocket,
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Origin not allowed",
        )
        return

    try:
        user = ensure_websocket_permission(
            websocket=websocket,
            lagoon_id=lagoon_id,
            permission=PERMISSION_VIEW,
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

    if not _is_valid_lagoon_id(lagoon_id):
        logger.warning(
            "[WS REJECTED] lagoon_id=%s client=%s code=%s reason=Lagoon not found",
            lagoon_id,
            client,
            status.WS_1008_POLICY_VIOLATION,
        )
        await _safe_close(
            websocket=websocket,
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Lagoon not found",
        )
        return

    user_id = str(user.get("sub", "unknown"))
    logger.debug(
        "[WS AUTHORIZED] lagoon_id=%s user_id=%s client=%s",
        lagoon_id,
        user_id,
        client,
    )
    await _serve_scada_stream(
        websocket=websocket,
        lagoon_id=lagoon_id,
        user_id=user_id,
        accept_subprotocol=accept_subprotocol,
    )


@router.websocket("/ws/scada/{lagoon_id}")
async def ws_scada_by_lagoon(
    websocket: WebSocket,
    lagoon_id: str,
):
    await _handle_scada_websocket(
        websocket=websocket,
        lagoon_id=lagoon_id,
    )
