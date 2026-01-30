from datetime import datetime
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
                    self._connections.pop(lagoon_id)

    async def broadcast(self, lagoon_id: str, tags: dict):
        payload = {
            "type": "tick",
            "lagoon_id": lagoon_id,
            "tags": tags,
            "ts": datetime.now().isoformat()
        }

        for ws in self.active_connections.get(lagoon_id, []):
            await ws.send_json(payload)
