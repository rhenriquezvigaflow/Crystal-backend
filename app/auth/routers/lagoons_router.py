from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.jwt import get_current_user
from app.auth.services.lagoon_service import (
    PERMISSION_CONTROL,
    PERMISSION_EDIT,
    get_accessible_lagoons,
    resolve_permitted_product_types,
    user_has_permission,
)
from app.core.logging import get_logger
from app.db.session import get_db
from app.security.rbac import ALL_READ_ROLES, extract_user_roles, require_permission, require_roles

router = APIRouter(tags=["Lagoons RBAC"])
logger = get_logger("api.lagoons")


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
    user: dict = Depends(require_roles(ALL_READ_ROLES)),
):
    user_id = _extract_user_id(user)
    email = str(user.get("email", "-"))
    roles = extract_user_roles(user)
    permitted_products = sorted(resolve_permitted_product_types(roles))
    lagoons = get_accessible_lagoons(
        db=db,
        user_id=user_id,
        user_roles=roles,
    )
    logger.info(
        "[LAGOONS SCOPE] user_id=%s email=%s roles=%s permitted_products=%s lagoons_count=%s",
        user_id,
        email,
        roles,
        permitted_products,
        len(lagoons),
    )
    return lagoons


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
