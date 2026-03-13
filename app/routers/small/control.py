from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.security.rbac import SMALL_WRITE_ROLES, require_roles

router = APIRouter(prefix="/api/small", tags=["Small Control"])


class ControlCommand(BaseModel):
    lagoon_id: str
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/control")
def send_control_command(
    cmd: ControlCommand,
    user: dict = Depends(require_roles(SMALL_WRITE_ROLES)),
):
    return {
        "ok": True,
        "product_type": "small",
        "lagoon_id": cmd.lagoon_id,
        "action": cmd.action,
        "requested_by": user.get("sub"),
    }


@router.put("/control")
def update_control_command(
    cmd: ControlCommand,
    user: dict = Depends(require_roles(SMALL_WRITE_ROLES)),
):
    return {
        "ok": True,
        "product_type": "small",
        "lagoon_id": cmd.lagoon_id,
        "action": cmd.action,
        "updated_by": user.get("sub"),
    }
