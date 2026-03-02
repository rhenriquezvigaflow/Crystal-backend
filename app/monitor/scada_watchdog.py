from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, text

from app.db.session import SessionLocal, engine
from app.models.scada_event import ScadaEvent
from app.models.scada_minute import ScadaMinute
from app.core.config import settings
from app.services.ingest_service import (
    reset_runtime_state,
    get_runtime_metrics,
)


@dataclass
class WatchdogSnapshot:
    minute_write_last: Optional[datetime]
    event_write_last: Optional[datetime]
    minute_write_age_sec: Optional[float]
    event_write_age_sec: Optional[float]


class ScadaStallWatchdog:
    """
    Watchdog PRO:
    - Evita falsos positivos al arranque (startup grace + baseline).
    - Señal primaria: tiempo desde la última ingesta en runtime.
    - Señal secundaria (fallback): tiempo desde la última escritura en BD.
    - Recuperación: reset memoria + kill idle-in-tx + dispose pool.
    - Hard restart opcional (último recurso).
    """

    def __init__(self) -> None:
        self.enabled = settings.SCADA_WATCHDOG_ENABLED
        self.check_interval_sec = settings.SCADA_WATCHDOG_CHECK_INTERVAL_SEC
        self.timeout_sec = settings.SCADA_WATCHDOG_TIMEOUT_SEC
        self.startup_grace_sec = settings.SCADA_WATCHDOG_STARTUP_GRACE_SEC
        self.recovery_cooldown_sec = settings.SCADA_WATCHDOG_RECOVERY_COOLDOWN_SEC
        self.hard_restart = settings.SCADA_WATCHDOG_HARD_RESTART

        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()

        self._boot_utc: datetime = datetime.now(timezone.utc)
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
            f"startup_grace={self.startup_grace_sec}s "
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
        while not self._stop.is_set():
            try:
                # 1) Respetar startup grace
                now_utc = datetime.now(timezone.utc)
                if (now_utc - self._boot_utc).total_seconds() < self.startup_grace_sec:
                    await self._sleep_interval()
                    continue

                # 2) Snapshot DB (para logging/fallback)
                snapshot = await asyncio.to_thread(self._read_snapshot)

                # 3) Señal primaria: runtime metrics
                runtime = get_runtime_metrics()
                if self._is_stalled(snapshot, runtime):
                    await self._recover(snapshot, runtime)

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"[WATCHDOG ERROR] {exc}")

            await self._sleep_interval()

    async def _sleep_interval(self) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=self.check_interval_sec)
        except asyncio.TimeoutError:
            pass

    # ===============================
    # DB SNAPSHOT
    # ===============================

    def _read_snapshot(self) -> WatchdogSnapshot:
        now_utc = datetime.now(timezone.utc)

        db = SessionLocal()
        try:
            minute_write_last = db.query(
                func.max(func.coalesce(ScadaMinute.updated_at, ScadaMinute.created_at))
            ).scalar()

            event_write_last = db.query(
                func.max(ScadaEvent.created_at)
            ).scalar()
        finally:
            db.close()

        minute_age = (
            (now_utc - minute_write_last).total_seconds()
            if minute_write_last else None
        )
        event_age = (
            (now_utc - event_write_last).total_seconds()
            if event_write_last else None
        )

        return WatchdogSnapshot(
            minute_write_last=minute_write_last,
            event_write_last=event_write_last,
            minute_write_age_sec=minute_age,
            event_write_age_sec=event_age,
        )

    # ===============================
    # STALL DETECTION
    # ===============================

    def _is_stalled(self, snapshot: WatchdogSnapshot, runtime: dict) -> bool:
    
        now_utc = datetime.now(timezone.utc)

        last_ingest_utc = runtime.get("last_ingest_utc")

        # Nunca hubo ingesta desde este runtime -> no podemos inferir stall real.
        if last_ingest_utc is None:
            return False

        # last_ingest_utc debe ser datetime (lo seteamos así en ingest_service)
        try:
            ingest_age = (now_utc - last_ingest_utc).total_seconds()
        except Exception:
            ingest_age = None

        if ingest_age is not None:
            return ingest_age > self.timeout_sec

        # Fallback: DB age
        if snapshot.minute_write_age_sec is None:
            return False

        return snapshot.minute_write_age_sec > self.timeout_sec

    # ===============================
    # RECOVERY
    # ===============================

    async def _recover(self, snapshot: WatchdogSnapshot, runtime: dict) -> None:
        now_utc = datetime.now(timezone.utc)

        # Cooldown entre recoveries
        if self._last_recovery_utc:
            elapsed = (now_utc - self._last_recovery_utc).total_seconds()
            if elapsed < self.recovery_cooldown_sec:
                return

        self._last_recovery_utc = now_utc

        print("\n========== WATCHDOG STALL DETECTED ==========")
        print(f"UTC: {now_utc.isoformat()}")
        print(f"Last lagoon: {runtime.get('last_lagoon')}")
        print(f"Last minute rows: {runtime.get('last_minute_rows')}")
        print(f"Last event count: {runtime.get('last_event_count')}")
        print(f"DB minute age sec: {snapshot.minute_write_age_sec}")
        print(f"DB event age sec: {snapshot.event_write_age_sec}")

        # 1) Reset memoria (buffer/last_state)
        reset_ok = await asyncio.to_thread(
            reset_runtime_state,
            "watchdog_stall",
            1.0,
        )

        # 2) Kill transacciones colgadas (idle in tx)
        killed = await asyncio.to_thread(self._terminate_stuck_transactions)

        # 3) Dispose pool (fuerza nuevas conexiones)
        await asyncio.to_thread(engine.dispose)

        print(
            "[WATCHDOG RECOVERY] "
            f"ingest_reset={reset_ok} "
            f"killed_idle_tx={killed} "
            "pool_disposed=True"
        )

        if self.hard_restart:
            print("[WATCHDOG] hard restart triggered")
            os._exit(1)

        print("========== WATCHDOG RECOVERY COMPLETE ==========\n")

    def _terminate_stuck_transactions(self) -> int:
        db = SessionLocal()
        try:
            res = db.execute(text("""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE state = 'idle in transaction'
                  AND xact_start IS NOT NULL
                  AND now() - xact_start > interval '60 seconds'
            """))
            db.commit()
            # rowcount puede ser -1 en algunos drivers; usamos fetchall si hace falta
            try:
                return int(res.rowcount) if res.rowcount is not None else 0
            except Exception:
                return 0
        finally:
            db.close()