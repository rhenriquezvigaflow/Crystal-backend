from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from app.alarms.notifier import dispatch_notifications
from app.alarms.service import (
    evaluate_lagoon_signal_alarms,
    log_persisted_alarm_transitions,
)
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import SessionLocal

logger = get_logger("alarms.silence_monitor")


class AlarmLagoonSignalMonitor:
    """
    Monitor por reloj para detectar lagunas sin senal.
    """

    def __init__(self) -> None:
        self.enabled = settings.ALARM_LAGOON_SIGNAL_MONITOR_ENABLED
        self.check_interval_sec = settings.ALARM_LAGOON_SIGNAL_CHECK_INTERVAL_SEC
        self.startup_grace_sec = settings.ALARM_LAGOON_SIGNAL_STARTUP_GRACE_SEC

        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self._boot_utc = datetime.now(timezone.utc)

    async def start(self) -> None:
        if not self.enabled:
            logger.info("[ALARM MONITOR] deshabilitado")
            return

        self._task = asyncio.create_task(self._run())
        logger.info(
            "[ALARM MONITOR] iniciado interval_sec=%s startup_grace_sec=%s",
            self.check_interval_sec,
            self.startup_grace_sec,
        )

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[ALARM MONITOR] detenido")

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.to_thread(self._check_once)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("[ALARM MONITOR ERROR]")

            try:
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=self.check_interval_sec,
                )
            except asyncio.TimeoutError:
                pass

    def _check_once(self) -> None:
        now_utc = datetime.now(timezone.utc)
        boot_age_sec = (now_utc - self._boot_utc).total_seconds()

        if boot_age_sec < self.startup_grace_sec:
            logger.info(
                "[ALARM MONITOR] startup_grace lagoon_checks_skipped=true boot_age_sec=%.1f startup_grace_sec=%.1f",
                boot_age_sec,
                self.startup_grace_sec,
            )
            return

        db = SessionLocal()
        transitions = []
        notification_jobs = []
        try:
            transitions, notification_jobs = evaluate_lagoon_signal_alarms(
                db=db,
                now_utc=now_utc,
            )
            db.commit()
            log_persisted_alarm_transitions(transitions)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        if transitions:
            logger.info(
                "[ALARM MONITOR] transiciones=%s at=%s",
                len(transitions),
                now_utc.isoformat(),
            )

        if notification_jobs:
            try:
                dispatch_notifications(notification_jobs)
            except Exception:
                logger.exception("[ALARM MONITOR NOTIFIER ERROR]")
