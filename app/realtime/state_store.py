from typing import Dict
from datetime import datetime
import asyncio


class StateStore:
    """
    Estado SCADA en memoria:
    lagoon_id -> { ts, tags }
    """

    def __init__(self):
        self._data: Dict[str, dict] = {}
        self._lock = asyncio.Lock()

    async def update(self, lagoon_id: str, ts: str, tags: dict):
        async with self._lock:
            self._data[lagoon_id] = {
                "ts": ts,
                "tags": tags,
            }

    async def get(self, lagoon_id: str):
        async with self._lock:
            return self._data.get(lagoon_id)
