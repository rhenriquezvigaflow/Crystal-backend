from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.alarms.thresholds.schemas import (
    ThresholdConfigRequest,
    ThresholdViewResponse,
    ThresholdUpsertResponse,
)
from app.alarms.thresholds.service import AlarmThresholdService
from app.auth.services.lagoon_service import (
    PERMISSION_EDIT,
    PERMISSION_VIEW,
    ensure_lagoon_access,
)
from app.core.logging import get_logger
from app.db.session import get_db
from app.security.rbac import ALL_READ_ROLES, extract_user_roles, require_roles

logger = get_logger("api.alarm.thresholds")
router = APIRouter(prefix="/alarms", tags=["Alarm Thresholds"])


def _extract_user_id(user: dict) -> str:
    user_id = user.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return user_id


@router.get(
    "/{lagoon_id}/thresholds/pt-fit/view",
    response_model=ThresholdViewResponse,
)
def get_pt_fit_thresholds_view(
    lagoon_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles(ALL_READ_ROLES)),
):
    user_id = _extract_user_id(user)
    ensure_lagoon_access(
        db=db,
        user_id=user_id,
        user_email=str(user.get("email", "-")),
        user_roles=extract_user_roles(user),
        lagoon_id=lagoon_id,
        permission=PERMISSION_VIEW,
    )

    try:
        rows = AlarmThresholdService.get_thresholds_view(
            db=db,
            lagoon_id=lagoon_id,
        )
    except Exception:
        AlarmThresholdService.log_exception(
            action="get_thresholds_view",
            lagoon_id=lagoon_id,
        )
        raise

    logger.info(
        "[API] endpoint_response_summary endpoint=/alarms/%s/thresholds/pt-fit/view user_id=%s rows_count=%s",
        lagoon_id,
        user_id,
        len(rows),
    )
    return {
        "lagoon_id": lagoon_id,
        "rows": rows,
    }


@router.put(
    "/{lagoon_id}/thresholds/pt-fit",
    response_model=ThresholdUpsertResponse,
)
def upsert_pt_fit_thresholds(
    lagoon_id: str,
    payload: ThresholdConfigRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles(ALL_READ_ROLES)),
):
    user_id = _extract_user_id(user)
    ensure_lagoon_access(
        db=db,
        user_id=user_id,
        user_email=str(user.get("email", "-")),
        user_roles=extract_user_roles(user),
        lagoon_id=lagoon_id,
        permission=PERMISSION_EDIT,
    )

    try:
        created_codes, updated_codes = AlarmThresholdService.upsert_thresholds(
            db=db,
            lagoon_id=lagoon_id,
            payload=payload,
        )
        db.commit()
    except Exception:
        db.rollback()
        first_tag = payload.items[0].tag_id if payload.items else None
        AlarmThresholdService.log_exception(
            action="upsert_thresholds",
            lagoon_id=lagoon_id,
            tag_id=first_tag,
            extra={"item_count": len(payload.items)},
        )
        raise

    logger.info(
        "[API] endpoint_response_summary endpoint=/alarms/%s/thresholds/pt-fit method=PUT user_id=%s created=%s updated=%s",
        lagoon_id,
        user_id,
        len(created_codes),
        len(updated_codes),
    )

    return {
        "ok": True,
        "lagoon_id": lagoon_id,
        "created": created_codes,
        "updated": updated_codes,
    }
