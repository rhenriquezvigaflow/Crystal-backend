from __future__ import annotations

import asyncio
import os
from collections import defaultdict
from typing import Any, DefaultDict, Set

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._connections: DefaultDict[str, Set[WebSocket]] = defaultdict(set)
        self._send_timeout_sec = float(
            os.getenv("WS_SEND_TIMEOUT_SEC", "2.0")
        )

    async def connect(self, lagoon_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections[lagoon_id].add(websocket)

    async def disconnect(self, lagoon_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            if lagoon_id in self._connections:
                self._connections[lagoon_id].discard(websocket)
                if not self._connections[lagoon_id]:
                    self._connections.pop(lagoon_id, None)

    async def _send_with_timeout(
        self,
        ws: WebSocket,
        message: dict[str, Any],
    ) -> bool:
        try:
            await asyncio.wait_for(
                ws.send_json(message),
                timeout=self._send_timeout_sec,
            )
            return True
        except Exception:
            return False

    async def broadcast(self, lagoon_id: str, message: dict[str, Any]) -> None:
        async with self._lock:
            sockets = list(self._connections.get(lagoon_id, set()))

        if not sockets:
            return

        results = await asyncio.gather(
            *(
                self._send_with_timeout(ws, message)
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
