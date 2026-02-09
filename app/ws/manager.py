from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, DefaultDict, Set

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._connections: DefaultDict[str, Set[WebSocket]] = defaultdict(set)

    async def connect(self, lagoon_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections[lagoon_id].add(websocket)

    async def disconnect(self, lagoon_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            if lagoon_id in self._connections:
                self._connections[lagoon_id].discard(websocket)
                if not self._connections[lagoon_id]:
                    self._connections.pop(lagoon_id, None)

    async def broadcast(self, lagoon_id: str, message: dict[str, Any]) -> None:
        async with self._lock:
            sockets = list(self._connections.get(lagoon_id, set()))

        to_remove: list[WebSocket] = []
        for ws in sockets:
            try:
                await ws.send_json(message)
            except Exception:
                to_remove.append(ws)

        if to_remove:
            async with self._lock:
                for ws in to_remove:
                    if lagoon_id in self._connections:
                        self._connections[lagoon_id].discard(ws)
