from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.services.lagoon_service import PERMISSION_VIEW, ensure_lagoon_access
from app.core.logging import get_logger
from app.db.session import get_db
from app.schemas.scada import ScadaSnapshot, ScadaCurrent
from app.services.scada_read_service import (
    get_last_minute,
    get_current,
)
from app.security.rbac import ALL_READ_ROLES, extract_user_roles, require_roles

router = APIRouter(prefix="/scada", tags=["SCADA"])
logger = get_logger("api.scada.read")


def _extract_user_id(user: dict) -> str:
    user_id = user.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return user_id


@router.get("/{lagoon_id}/last-minute", response_model=ScadaSnapshot)
def last_minute(
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
    data = get_last_minute(lagoon_id, db)
    if not data:
        raise HTTPException(404, "No data")
    logger.info(
        "[API] endpoint_response_summary endpoint=/scada/%s/last-minute user_id=%s tags_count=%s",
        lagoon_id,
        user_id,
        len(data.get("tags", {})),
    )
    return data


@router.get("/{lagoon_id}/current", response_model=ScadaCurrent)
def current(
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
    data = get_current(lagoon_id, db)
    if not data:
        raise HTTPException(404, "No data")
    logger.info(
        "[API] endpoint_response_summary endpoint=/scada/%s/current user_id=%s tags_count=%s",
        lagoon_id,
        user_id,
        len(data.get("tags", {})),
    )
    return data
