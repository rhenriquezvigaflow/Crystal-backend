from typing import Dict, Set
from fastapi import WebSocket
import asyncio


class WebSocketManager:
    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, lagoon_id: str, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._connections.setdefault(lagoon_id, set()).add(ws)

    async def disconnect(self, lagoon_id: str, ws: WebSocket):
        async with self._lock:
            if lagoon_id in self._connections:
                self._connections[lagoon_id].discard(ws)
                if not self._connections[lagoon_id]:
                    self._connections.pop(lagoon_id, None)

    async def broadcast(self, lagoon_id: str, message: dict):
        async with self._lock:
            conns = list(self._connections.get(lagoon_id, []))

        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                await self.disconnect(lagoon_id, ws)
