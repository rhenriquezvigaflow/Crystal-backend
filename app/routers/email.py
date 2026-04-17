from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.alarms.notifier import dispatch_notifications
from app.core.logging import get_logger
from app.integration.notifications import notification_orchestrator
from app.schemas.notifications import EmailTestAlertRequest
from app.security.rbac import ALL_READ_ROLES, require_roles

logger = get_logger("api.email")
router = APIRouter(prefix="/email", tags=["Email Notifications"])


def _extract_user_id(user: dict) -> str:
    user_id = user.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return user_id


@router.post(
    "/test-alert",
    status_code=status.HTTP_202_ACCEPTED,
)
async def send_test_alert_email(
    payload: EmailTestAlertRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_roles(ALL_READ_ROLES)),
):
    if not notification_orchestrator.email_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SMTP email settings are not configured",
        )

    notification_job = notification_orchestrator.build_email_job(
        payload.to_alarm_payload()
    )
    requested_by = _extract_user_id(user)

    background_tasks.add_task(
        dispatch_notifications,
        [notification_job],
    )

    logger.info(
        "[EMAIL TEST QUEUED] user_id=%s lagoon_id=%s recipients=%s",
        requested_by,
        payload.lagoon_id,
        len(notification_job.alarm_payload.recipients)
        if notification_job.alarm_payload is not None
        else 0,
    )

    return {
        "ok": True,
        "queued": True,
        "lagoon_id": payload.lagoon_id,
        "recipients": [
            str(item)
            for item in payload.recipients
        ],
    }
