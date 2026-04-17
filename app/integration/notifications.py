from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Sequence

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.notifications import (
    AlarmNotificationPayload,
    NotificationChannel,
    NotificationJob,
)
from app.services.email_service import EmailService

logger = get_logger("alarms.notification.orchestrator")


class NotificationOrchestrator:
    """
    Orquesta el despacho de canales sin acoplarlos al motor de alarmas.

    El motor produce `NotificationJob` post-commit y esta capa resuelve
    el canal concreto de entrega.
    """

    def __init__(
        self,
        *,
        email_service: EmailService | None = None,
        max_workers: int | None = None,
    ) -> None:
        self.email_service = email_service or EmailService()
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers or max(settings.MAIL_DISPATCH_MAX_WORKERS, 1),
            thread_name_prefix="notification",
        )

    def dispatch(self, jobs: Sequence[NotificationJob]) -> None:
        if not jobs:
            return

        for job in jobs:
            self._executor.submit(self._dispatch_job_safe, job)

    def dispatch_now(self, jobs: Sequence[NotificationJob]) -> None:
        for job in jobs:
            self._dispatch_job_safe(job)

    def build_email_job(
        self,
        payload: AlarmNotificationPayload,
    ) -> NotificationJob:
        recipients = ",".join(str(item) for item in payload.recipients)
        return NotificationJob(
            channel=NotificationChannel.email.value,
            target=recipients,
            transition=payload.transition,
            alarm_type=payload.category,
            severity=payload.priority,
            lagoon_id=payload.lagoon_id,
            tag_id=payload.tag_id,
            event_id=payload.event_id,
            happened_at=payload.timestamp,
            message=payload.description,
            alarm_payload=payload,
        )

    def _dispatch_job_safe(self, job: NotificationJob) -> None:
        try:
            self._dispatch_job(job)
        except Exception:
            logger.exception(
                "[NOTIFY ERROR] channel=%s target=%s event=%s lagoon=%s",
                job.channel,
                job.target,
                job.event_id,
                job.lagoon_id,
            )

    def _dispatch_job(self, job: NotificationJob) -> None:
        if job.channel == NotificationChannel.email.value:
            self._dispatch_email(job)
            return

        if job.channel == NotificationChannel.webhook.value:
            self._dispatch_webhook(job)
            return

        logger.warning(
            "[NOTIFY SKIP] reason=unsupported_channel channel=%s target=%s event=%s",
            job.channel,
            job.target,
            job.event_id,
        )

    def _dispatch_email(self, job: NotificationJob) -> None:
        payload = job.alarm_payload
        if payload is None:
            logger.warning(
                "[EMAIL SKIP] reason=missing_payload target=%s event=%s",
                job.target,
                job.event_id,
            )
            return

        self.email_service.send_alarm_notification_sync(payload)
        logger.info(
            "[EMAIL SENT] event=%s lagoon=%s tag=%s recipients=%s subject=%s",
            job.event_id,
            job.lagoon_id,
            job.tag_id,
            len(payload.recipients),
            payload.subject,
        )

    def _dispatch_webhook(self, job: NotificationJob) -> None:
        logger.info(
            "[WEBHOOK SIMULATED] url=%s transition=%s type=%s severity=%s lagoon=%s tag=%s event=%s payload=%s",
            job.target,
            job.transition,
            job.alarm_type,
            job.severity,
            job.lagoon_id,
            job.tag_id,
            job.event_id,
            job.message,
        )


notification_orchestrator = NotificationOrchestrator()
