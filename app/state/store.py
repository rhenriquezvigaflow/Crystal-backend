from __future__ import annotations
from typing import Dict, Any
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


class RealtimeStateStore:

    def __init__(self) -> None:
        self._tags: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self._last_ts: Dict[str, str] = {}
        self._pump_last_on: Dict[str, Dict[str, str]] = defaultdict(dict)
        self._start_ts: Dict[str, str] = {}

        # Nuevo: timezone por laguna (precargado desde BD)
        self._lagoon_timezone: Dict[str, str] = {}

    # =====================================================
    # CONFIG
    # =====================================================

    def set_lagoon_timezone(self, lagoon_id: str, timezone_str: str):
        self._lagoon_timezone[lagoon_id] = timezone_str

    def preload_state(self, lagoon_id: str, tags: Dict[str, Any]):
        self._tags[lagoon_id].update(tags)

    def set_pump_last_on(self, lagoon_id: str, tag_id: str, ts: str):
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

        self._tags[lagoon_id].update(tags)
        self._last_ts[lagoon_id] = ts

        if pump_last_on_updates:
            for tag_id, start_ts in pump_last_on_updates.items():
                self._pump_last_on[lagoon_id][tag_id] = start_ts
                self._start_ts[lagoon_id] = start_ts

    # =====================================================
    # INTERNAL HELPERS
    # =====================================================

    def _compute_plc_status(self, lagoon_id: str, timeout_sec: int = 10) -> str:
        last_ts = self._last_ts.get(lagoon_id)
        if not last_ts:
            return "offline"

        try:
            last_dt = datetime.fromisoformat(last_ts)
            now = datetime.now(timezone.utc)
            diff = (now - last_dt).total_seconds()
            return "online" if diff <= timeout_sec else "offline"
        except Exception:
            return "offline"

    def _compute_local_time(self, lagoon_id: str) -> str | None:
        last_ts = self._last_ts.get(lagoon_id)
        tz_str = self._lagoon_timezone.get(lagoon_id)

        if not last_ts or not tz_str:
            return None

        try:
            utc_dt = datetime.fromisoformat(last_ts)
            local_dt = utc_dt.astimezone(ZoneInfo(tz_str))
            return local_dt.strftime("%H:%M:%S")
        except Exception:
            return None

    # =====================================================
    # PAYLOAD
    # =====================================================

    def _payload(self, lagoon_id: str, payload_type: str) -> dict:
        return {
            "type": payload_type,
            "lagoon_id": lagoon_id,
            "ts": self._last_ts.get(lagoon_id),
            "plc_status": self._compute_plc_status(lagoon_id),
            "local_time": self._compute_local_time(lagoon_id),
            "timezone": self._lagoon_timezone.get(lagoon_id),
            "tags": dict(self._tags.get(lagoon_id, {})),
            "pump_last_on": dict(self._pump_last_on.get(lagoon_id, {})),
            "start_ts": self._start_ts.get(lagoon_id),
        }

    def snapshot(self, lagoon_id: str) -> dict:
        return self._payload(lagoon_id, "snapshot")

    async def tick_payload(self, lagoon_id: str) -> dict:
        return self._payload(lagoon_id, "tick")