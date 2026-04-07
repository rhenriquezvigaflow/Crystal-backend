# app/persist/worker.py
import asyncio
from typing import Optional

from app.alarms.notifier import dispatch_notifications
from app.alarms.service import evaluate_alarms
from app.core.logging import get_logger
from app.persist.queue import persist_queue
from app.db.session import SessionLocal
from app.services.ingest_service import ingest

logger = get_logger("persist.worker")


class PersistWorker:
    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()

    async def start(self):
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        self._stop.set()
        if self._task:
            self._task.cancel()

    async def _run(self):
        while not self._stop.is_set():
            try:
                tick = await persist_queue.get()
            except asyncio.CancelledError:
                break

            db = SessionLocal()
            try:
                ingest(
                    lagoon_id=tick.lagoon_id,
                    ts=tick.timestamp,
                    tags=tick.tags,
                    db=db,
                )
                _, notification_jobs = evaluate_alarms(
                    payload={
                        "lagoon_id": tick.lagoon_id,
                        "timestamp": tick.timestamp,
                        "tags": tick.tags,
                    },
                    db=db,
                )
                db.commit()

                if notification_jobs:
                    try:
                        dispatch_notifications(notification_jobs)
                    except Exception:
                        logger.exception(
                            "[PERSIST WORKER ERROR NOTIFICADOR] lagoon_id=%s",
                            tick.lagoon_id,
                        )
            except Exception:
                db.rollback()
            finally:
                db.close()
                persist_queue.task_done()
