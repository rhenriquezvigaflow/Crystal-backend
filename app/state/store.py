# app/state/store.py
from collections import defaultdict, deque
from typing import Any, Dict, Tuple

RING_SECONDS = 15

class RealtimeStateStore:
    def __init__(self) -> None:
        self.latest: Dict[str, Dict[str, Tuple[Any, str]]] = defaultdict(dict)
        self.ring: Dict[str, deque] = defaultdict(lambda: deque(maxlen=RING_SECONDS))

    def update(self, lagoon_id: str, ts: str, tags: Dict[str, Any]) -> None:
        for tag_id, val in tags.items():
            self.latest[lagoon_id][tag_id] = (val, ts)

        self.ring[lagoon_id].append({
            "type": "tick",
            "lagoon_id": lagoon_id,
            "ts": ts,
            "tags": tags,
        })

    def snapshot(self, lagoon_id: str) -> dict:
        tags = {k: v for k, (v, _) in self.latest.get(lagoon_id, {}).items()}
        return {
            "type": "snapshot",
            "lagoon_id": lagoon_id,
            "tags": tags,
        }
