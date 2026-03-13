from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.jwt import get_current_user
from app.auth.services.lagoon_service import (
    PERMISSION_CONTROL,
    PERMISSION_EDIT,
    PERMISSION_VIEW,
    get_accessible_lagoons,
    user_has_permission,
)
from app.db.session import get_db
from app.security.rbac import require_permission

router = APIRouter(tags=["Lagoons RBAC"])


class LagoonEditRequest(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


class PumpControlRequest(BaseModel):
    lagoon_id: str
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)


def _extract_user_id(user: dict) -> str:
    user_id = user.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return user_id


@router.get("/lagoons")
def list_lagoons(
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission(PERMISSION_VIEW, lagoon_id_param=None)),
):
    user_id = _extract_user_id(user)
    return get_accessible_lagoons(db=db, user_id=user_id)


@router.put("/lagoons/{id}")
def update_lagoon(
    id: str,
    body: LagoonEditRequest,
    user: dict = Depends(require_permission(PERMISSION_EDIT, lagoon_id_param="id")),
):
    user_id = _extract_user_id(user)
    return {
        "ok": True,
        "lagoon_id": id,
        "changes": body.values,
        "updated_by": user_id,
    }


@router.post("/control/pump")
def control_pump(
    cmd: PumpControlRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = _extract_user_id(user)
    if not user_has_permission(
        db=db,
        user_id=user_id,
        lagoon_id=cmd.lagoon_id,
        permission=PERMISSION_CONTROL,
    ):
        raise HTTPException(status_code=403, detail="Forbidden")

    return {
        "ok": True,
        "lagoon_id": cmd.lagoon_id,
        "action": cmd.action,
        "payload": cmd.payload,
        "requested_by": user_id,
    }
