from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func

from app.db.session import SessionLocal, engine
from app.models.scada_event import ScadaEvent
from app.models.scada_minute import ScadaMinute
from app.core.config import settings
from app.services.ingest_service import reset_runtime_state


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class WatchdogSnapshot:
    minute_last: Optional[datetime]
    event_last: Optional[datetime]
    minute_age_sec: Optional[float]
    event_age_sec: Optional[float]


class ScadaStallWatchdog:
    def __init__(self) -> None:
        self.enabled = settings.SCADA_WATCHDOG_ENABLED
        self.check_interval_sec = settings.SCADA_WATCHDOG_CHECK_INTERVAL_SEC
        self.timeout_sec = settings.SCADA_WATCHDOG_TIMEOUT_SEC
        self.startup_grace_sec = settings.SCADA_WATCHDOG_STARTUP_GRACE_SEC
        self.recovery_cooldown_sec = (
            settings.SCADA_WATCHDOG_RECOVERY_COOLDOWN_SEC
        )
        self.hard_restart = settings.SCADA_WATCHDOG_HARD_RESTART

        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self._last_recovery_utc: Optional[datetime] = None

    async def start(self) -> None:
        if not self.enabled:
            print("[WATCHDOG] disabled")
            return

        self._task = asyncio.create_task(self._run())
        print(
            "[WATCHDOG] started "
            f"timeout={self.timeout_sec}s "
            f"interval={self.check_interval_sec}s "
            f"hard_restart={self.hard_restart}"
        )

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        print("[WATCHDOG] stopped")

    async def _run(self) -> None:
        if self.startup_grace_sec > 0:
            try:
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=self.startup_grace_sec,
                )
                return
            except asyncio.TimeoutError:
                pass

        while not self._stop.is_set():
            try:
                snapshot = await asyncio.to_thread(
                    self._read_snapshot
                )
                if self._is_stalled(snapshot):
                    await self._recover(snapshot)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"[WATCHDOG ERROR] {exc}")

            try:
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=self.check_interval_sec,
                )
            except asyncio.TimeoutError:
                pass

    def _read_snapshot(self) -> WatchdogSnapshot:
        now_utc = datetime.now(timezone.utc)
        db = SessionLocal()
        try:
            minute_last = db.query(
                func.max(ScadaMinute.bucket)
            ).scalar()
            event_last = db.query(
                func.max(
                    func.coalesce(
                        ScadaEvent.end_ts,
                        ScadaEvent.start_ts,
                        ScadaEvent.created_at,
                    )
                )
            ).scalar()
        finally:
            db.close()

        minute_last = _as_utc(minute_last)
        event_last = _as_utc(event_last)

        minute_age_sec = (
            (now_utc - minute_last).total_seconds()
            if minute_last else None
        )
        event_age_sec = (
            (now_utc - event_last).total_seconds()
            if event_last else None
        )

        return WatchdogSnapshot(
            minute_last=minute_last,
            event_last=event_last,
            minute_age_sec=minute_age_sec,
            event_age_sec=event_age_sec,
        )

    def _is_stalled(self, snapshot: WatchdogSnapshot) -> bool:
        if snapshot.minute_last is None and snapshot.event_last is None:
            return False

        minute_stale = (
            snapshot.minute_age_sec is None
            or snapshot.minute_age_sec > self.timeout_sec
        )
        event_stale = (
            snapshot.event_age_sec is None
            or snapshot.event_age_sec > self.timeout_sec
        )

        return minute_stale and event_stale

    async def _recover(self, snapshot: WatchdogSnapshot) -> None:
        now_utc = datetime.now(timezone.utc)

        if self._last_recovery_utc:
            elapsed = (
                now_utc - self._last_recovery_utc
            ).total_seconds()
            if elapsed < self.recovery_cooldown_sec:
                return

        self._last_recovery_utc = now_utc

        print(
            "[WATCHDOG STALL] "
            f"minute_age={snapshot.minute_age_sec} "
            f"event_age={snapshot.event_age_sec}"
        )

        reset_ok = await asyncio.to_thread(
            reset_runtime_state,
            "watchdog_stall",
            1.0,
        )
        await asyncio.to_thread(engine.dispose)

        print(
            "[WATCHDOG RECOVERY] "
            f"ingest_reset={reset_ok} pool_disposed=True"
        )

        if self.hard_restart:
            print("[WATCHDOG] hard restart triggered")
            os._exit(1)
