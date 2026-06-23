from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.small_control_audit import SmallControlAudit


def begin_control_audit(
    db: Session,
    *,
    lagoon_id: str,
    module_id: str,
    control_type: str,
    action: str,
    change_summary: str,
    user_id: str,
    user_email: str,
    command_id: str | None = None,
    new_value: Any | None = None,
) -> SmallControlAudit:
    audit = SmallControlAudit(
        lagoon_id=lagoon_id,
        module_id=module_id,
        control_type=control_type,
        action=action,
        command_id=command_id,
        new_value=new_value,
        change_summary=change_summary,
        status="pending",
        user_id=user_id,
        user_email=user_email,
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit


def complete_control_audit(
    db: Session,
    audit: SmallControlAudit,
    *,
    module_id: str | None = None,
    tag_id: str | None = None,
    node_id: str | None = None,
    previous_value: Any | None = None,
    new_value: Any | None = None,
    change_summary: str | None = None,
) -> None:
    if module_id:
        audit.module_id = module_id
    audit.tag_id = tag_id
    audit.node_id = node_id
    audit.previous_value = previous_value
    if new_value is not None:
        audit.new_value = new_value
    if change_summary:
        audit.change_summary = change_summary
    audit.status = "success"
    audit.error_detail = None
    audit.completed_at = datetime.now(timezone.utc)
    db.commit()


def fail_control_audit(
    db: Session,
    audit: SmallControlAudit,
    error: Exception,
) -> None:
    audit.status = "failed"
    audit.error_detail = str(error)[:1000]
    audit.completed_at = datetime.now(timezone.utc)
    db.commit()
