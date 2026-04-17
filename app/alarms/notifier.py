from __future__ import annotations

from typing import Sequence

from app.integration.notifications import notification_orchestrator
from app.schemas.notifications import NotificationJob


def dispatch_notifications(
    jobs: Sequence[NotificationJob],
) -> None:
    notification_orchestrator.dispatch(jobs)
