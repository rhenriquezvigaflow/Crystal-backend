from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

from app.core.logging import get_logger

logger = get_logger("alarms.notifier")


@dataclass(slots=True)
class NotificationJob:
    """
    Mensaje emitido por el evaluador de alarmas y despachado por canal.
    """

    channel: str
    target: str
    transition: str
    alarm_type: str
    severity: str
    lagoon_id: str
    tag_id: str | None
    event_id: str
    happened_at: datetime
    message: str


def dispatch_notifications(
    jobs: Sequence[NotificationJob],
) -> None:
    """
    Despacha trabajos de notificacion.

    Implementacion mock para canales email/webhook.
    Registra por log el payload renderizado sin efectos externos.
    """
    if not jobs:
        return

    for job in jobs:
        if job.channel == "email":
            _dispatch_email(job)
            continue

        if job.channel == "webhook":
            _dispatch_webhook(job)
            continue

        logger.warning(
            "[ALARMAS NOTIFICACION CANAL NO SOPORTADO] canal=%s destino=%s evento_id=%s",
            job.channel,
            job.target,
            job.event_id,
        )


def _dispatch_email(job: NotificationJob) -> None:
    logger.info(
        "[CORREO SIMULADO] para=%s transicion=%s severidad=%s lagoon_id=%s tag_id=%s evento_id=%s fecha=%s cuerpo=%s",
        job.target,
        job.transition,
        job.severity,
        job.lagoon_id,
        job.tag_id,
        job.event_id,
        _to_iso_utc(job.happened_at),
        job.message,
    )


def _dispatch_webhook(job: NotificationJob) -> None:
    logger.info(
        "[WEBHOOK SIMULADO] url=%s transicion=%s tipo_alarma=%s severidad=%s lagoon_id=%s tag_id=%s evento_id=%s fecha=%s payload=%s",
        job.target,
        job.transition,
        job.alarm_type,
        job.severity,
        job.lagoon_id,
        job.tag_id,
        job.event_id,
        _to_iso_utc(job.happened_at),
        job.message,
    )


def _to_iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
