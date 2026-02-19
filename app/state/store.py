from __future__ import annotations
from typing import Dict, Any
from collections import defaultdict


class RealtimeStateStore:

    def __init__(self) -> None:
        # Últimos valores crudos por laguna
        self._tags: Dict[str, Dict[str, Any]] = defaultdict(dict)

        # Último timestamp recibido por laguna
        self._last_ts: Dict[str, str] = {}

        # Última hora ON por bomba
        self._pump_last_on: Dict[str, Dict[str, str]] = defaultdict(dict)

        # Último evento start_ts general por laguna
        self._start_ts: Dict[str, str] = {}


    def preload_state(self, lagoon_id: str, tags: Dict[str, Any]):
        """
        Carga estado inicial desde BD (para sincronización post-restart).
        """
        self._tags[lagoon_id].update(tags)

    def set_pump_last_on(self, lagoon_id: str, tag_id: str, ts: str):
        """
        Set explícito desde boot o ingest.
        """
        self._pump_last_on[lagoon_id][tag_id] = ts

    def set_start_ts(self, lagoon_id: str, ts: str):
        self._start_ts[lagoon_id] = ts

    # =====================================================
    # UPDATE REALTIME 
    # =====================================================

    async def update(
        self,
        lagoon_id: str,
        tags: Dict[str, Any],
        ts: str,
        pump_last_on_updates: Dict[str, str] | None = None,
    ):

        # Update tags
        self._tags[lagoon_id].update(tags)

        # Update timestamp
        self._last_ts[lagoon_id] = ts

        # Update bombas si ingest lo indica
        if pump_last_on_updates:
            for tag_id, start_ts in pump_last_on_updates.items():
                self._pump_last_on[lagoon_id][tag_id] = start_ts
                self._start_ts[lagoon_id] = start_ts


    def _payload(self, lagoon_id: str, payload_type: str) -> dict:
        return {
            "type": payload_type,
            "lagoon_id": lagoon_id,
            "ts": self._last_ts.get(lagoon_id),
            "tags": dict(self._tags.get(lagoon_id, {})),
            "pump_last_on": dict(self._pump_last_on.get(lagoon_id, {})),
            "start_ts": self._start_ts.get(lagoon_id),
        }

    def snapshot(self, lagoon_id: str) -> dict:
        return self._payload(lagoon_id, "snapshot")

    async def tick_payload(self, lagoon_id: str) -> dict:
        return self._payload(lagoon_id, "tick")
