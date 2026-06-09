from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.services.lagoon_service import (
    PERMISSION_CONTROL,
    ensure_lagoon_access,
)
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.role import ProductType
from app.security.rbac import SMALL_WRITE_ROLES, extract_user_roles, require_roles

router = APIRouter(prefix="/small", tags=["Small Control"])
logger = get_logger("api.small.control")


class ControlCommand(BaseModel):
    lagoon_id: str
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)


def _extract_user_id(user: dict) -> str:
    user_id = user.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return user_id


@router.post("/control")
def send_control_command(
    cmd: ControlCommand,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles(SMALL_WRITE_ROLES)),
):
    user_id = _extract_user_id(user)
    email = str(user.get("email", "-"))
    roles = extract_user_roles(user)
    ensure_lagoon_access(
        db=db,
        user_id=user_id,
        user_email=email,
        user_roles=roles,
        lagoon_id=cmd.lagoon_id,
        permission=PERMISSION_CONTROL,
        expected_product_type=ProductType.SMALL,
    )
    logger.info(
        "[API] endpoint_response_summary endpoint=/api/small/control method=POST user_id=%s lagoon_id=%s action=%s",
        user_id,
        cmd.lagoon_id,
        cmd.action,
    )
    return {
        "ok": True,
        "product_type": "small",
        "lagoon_id": cmd.lagoon_id,
        "action": cmd.action,
        "requested_by": user_id,
    }


@router.put("/control")
def update_control_command(
    cmd: ControlCommand,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles(SMALL_WRITE_ROLES)),
):
    user_id = _extract_user_id(user)
    email = str(user.get("email", "-"))
    roles = extract_user_roles(user)
    ensure_lagoon_access(
        db=db,
        user_id=user_id,
        user_email=email,
        user_roles=roles,
        lagoon_id=cmd.lagoon_id,
        permission=PERMISSION_CONTROL,
        expected_product_type=ProductType.SMALL,
    )
    logger.info(
        "[API] endpoint_response_summary endpoint=/api/small/control method=PUT user_id=%s lagoon_id=%s action=%s",
        user_id,
        cmd.lagoon_id,
        cmd.action,
    )
    return {
        "ok": True,
        "product_type": "small",
        "lagoon_id": cmd.lagoon_id,
        "action": cmd.action,
        "updated_by": user_id,
    }
