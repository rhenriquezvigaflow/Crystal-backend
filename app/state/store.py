from __future__ import annotations
from typing import Dict, Any


class RealtimeStateStore:
    def __init__(self) -> None:
        self.tags: Dict[str, Dict[str, Any]] = {}
        self.last_ts: Dict[str, str] = {}

        self.start_ts: Dict[str, str] = {}
        self.pump_last_on: Dict[str, Dict[str, str]] = {}

    async def preload_last_start_ts(self, lagoon_id: str, ts: str | None):
        if ts:
            self.start_ts[lagoon_id] = ts

    async def update(self, lagoon_id: str, tags: dict, ts: str):
        prev_tags = self.tags.get(lagoon_id, {})

        self.tags.setdefault(lagoon_id, {})
        self.pump_last_on.setdefault(lagoon_id, {})

        for tag, value in tags.items():
            if isinstance(value, bool):
                prev = prev_tags.get(tag)

                if value is True and (prev is False or prev is None):
                    self.pump_last_on[lagoon_id][tag] = ts
                    self.start_ts[lagoon_id] = ts

        self.tags[lagoon_id].update(tags)
        self.last_ts[lagoon_id] = ts

    def snapshot(self, lagoon_id: str) -> dict:
        return {
            "type": "snapshot",
            "lagoon_id": lagoon_id,
            "ts": self.last_ts.get(lagoon_id),
            "tags": self.tags.get(lagoon_id, {}),
            "pump_last_on": self.pump_last_on.get(lagoon_id, {}),
            "start_ts": {lagoon_id: self.start_ts.get(lagoon_id)},
        }

    async def tick_payload(self, lagoon_id: str) -> dict:
        return {
            "type": "tick",
            "lagoon_id": lagoon_id,
            "ts": self.last_ts.get(lagoon_id),
            "tags": self.tags.get(lagoon_id, {}),
            "pump_last_on": self.pump_last_on.get(lagoon_id, {}),
            "start_ts": {lagoon_id: self.start_ts.get(lagoon_id)},
        }
