from __future__ import annotations

import asyncio
import os
from collections import defaultdict
from typing import Any, DefaultDict, Set

from fastapi import WebSocket, status

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("ws.manager")


def _client_label(websocket: WebSocket) -> str:
    client = websocket.client
    return f"{getattr(client, 'host', 'unknown')}:{getattr(client, 'port', 'unknown')}"


def _is_truthy(raw_value: str) -> bool:
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


WS_VERBOSE_TICK_LOGS = _is_truthy(
    os.getenv("WS_VERBOSE_TICK_LOGS", "0")
)


def _tick_log(message_type: object):
    if str(message_type).lower() == "tick" and not WS_VERBOSE_TICK_LOGS:
        return logger.debug
    return logger.info


class WebSocketManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._connections: DefaultDict[str, Set[WebSocket]] = defaultdict(set)
        self._send_timeout_sec = max(
            float(settings.WS_MIN_SEND_TIMEOUT_SEC),
            float(settings.WS_SEND_TIMEOUT_SEC),
        )

    async def connect(self, lagoon_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections[lagoon_id].add(websocket)
            count = len(self._connections[lagoon_id])
        logger.debug(
            "[WS MANAGER CONNECT] lagoon_id=%s client=%s:%s connections=%s",
            lagoon_id,
            getattr(websocket.client, "host", "unknown"),
            getattr(websocket.client, "port", "unknown"),
            count,
        )

    def stats(self) -> dict[str, object]:
        lagoon_counts = {
            lagoon_id: len(sockets)
            for lagoon_id, sockets in self._connections.items()
        }
        return {
            "lagoon_count": len(lagoon_counts),
            "total_connections": sum(lagoon_counts.values()),
            "connections_by_lagoon": lagoon_counts,
        }

    async def disconnect(self, lagoon_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            if lagoon_id in self._connections:
                self._connections[lagoon_id].discard(websocket)
                if not self._connections[lagoon_id]:
                    self._connections.pop(lagoon_id, None)
                    count = 0
                else:
                    count = len(self._connections[lagoon_id])
            else:
                count = 0
        logger.debug(
            "[WS MANAGER DISCONNECT] lagoon_id=%s client=%s:%s connections=%s",
            lagoon_id,
            getattr(websocket.client, "host", "unknown"),
            getattr(websocket.client, "port", "unknown"),
            count,
        )

    async def _send_with_timeout(
        self,
        lagoon_id: str,
        ws: WebSocket,
        message: dict[str, Any],
    ) -> bool:
        msg_type = message.get("type")
        client = _client_label(ws)
        _tick_log(msg_type)(
            "[WS MANAGER SEND START] lagoon_id=%s client=%s type=%s",
            lagoon_id,
            client,
            msg_type,
        )
        try:
            await asyncio.wait_for(
                ws.send_json(message),
                timeout=self._send_timeout_sec,
            )
            _tick_log(msg_type)(
                "[WS MANAGER SEND OK] lagoon_id=%s client=%s type=%s",
                lagoon_id,
                client,
                msg_type,
            )
            return True
        except asyncio.TimeoutError:
            logger.warning(
                "[WS SEND TIMEOUT] lagoon_id=%s client=%s type=%s timeout_sec=%s",
                lagoon_id,
                client,
                msg_type,
                self._send_timeout_sec,
            )
            return False
        except Exception:
            logger.exception(
                "[WS SEND ERROR] lagoon_id=%s client=%s type=%s",
                lagoon_id,
                client,
                msg_type,
            )
            return False

    async def broadcast(self, lagoon_id: str, message: dict[str, Any]) -> None:
        async with self._lock:
            sockets = list(self._connections.get(lagoon_id, set()))
        msg_type = message.get("type")

        if not sockets:
            _tick_log(msg_type)(
                "[WS BROADCAST SKIP] lagoon_id=%s reason=no_connections type=%s",
                lagoon_id,
                msg_type,
            )
            return

        _tick_log(msg_type)(
            "[WS BROADCAST START] lagoon_id=%s sockets=%s type=%s",
            lagoon_id,
            len(sockets),
            msg_type,
        )

        results = await asyncio.gather(
            *(
                self._send_with_timeout(lagoon_id, ws, message)
                for ws in sockets
            ),
            return_exceptions=False,
        )

        to_remove = [
            ws for ws, ok in zip(sockets, results)
            if not ok
        ]

        if to_remove:
            async with self._lock:
                for ws in to_remove:
                    if lagoon_id in self._connections:
                        self._connections[lagoon_id].discard(ws)
                remaining = len(self._connections.get(lagoon_id, set()))
                if lagoon_id in self._connections and remaining == 0:
                    self._connections.pop(lagoon_id, None)

            for ws in to_remove:
                logger.warning(
                    "[WS MANAGER REMOVE] lagoon_id=%s client=%s reason=send_failure",
                    lagoon_id,
                    _client_label(ws),
                )
                try:
                    await ws.close(code=status.WS_1001_GOING_AWAY)
                except RuntimeError:
                    continue
                except Exception:
                    logger.exception(
                        "[WS CLEANUP CLOSE ERROR] lagoon_id=%s",
                        lagoon_id,
                    )

            logger.warning(
                "[WS BROADCAST CLEANUP] lagoon_id=%s removed=%s remaining=%s",
                lagoon_id,
                len(to_remove),
                remaining,
            )
        else:
            _tick_log(msg_type)(
                "[WS BROADCAST DONE] lagoon_id=%s delivered=%s type=%s",
                lagoon_id,
                len(sockets),
                msg_type,
            )
