from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth.services.lagoon_service import (
    PERMISSION_VIEW,
    ensure_lagoon_access,
)
from app.security.rbac import extract_user_roles


def extract_user_id(user: dict) -> str:
    user_id = user.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return user_id


def ensure_scada_read_access(
    *,
    db: Session,
    user: dict,
    lagoon_id: str,
) -> tuple[str, list[str]]:
    user_id = extract_user_id(user)
    roles = extract_user_roles(user)
    ensure_lagoon_access(
        db=db,
        user_id=user_id,
        user_email=str(user.get("email", "-")),
        user_roles=roles,
        lagoon_id=lagoon_id,
        permission=PERMISSION_VIEW,
    )
    return user_id, roles
