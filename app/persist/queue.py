# app/persist/queue.py
import asyncio
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class PersistTick:
    lagoon_id: str
    timestamp: str  # ISO UTC
    tags: Dict[str, Any]

persist_queue: asyncio.Queue[PersistTick] = asyncio.Queue(maxsize=200_000)
