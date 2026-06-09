from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.services.lagoon_service import (
    PERMISSION_EDIT,
    ensure_lagoon_access,
)
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.role import ProductType
from app.security.rbac import SMALL_READ_ROLES, SMALL_WRITE_ROLES, extract_user_roles, require_roles

router = APIRouter(prefix="/small", tags=["Small Chemicals"])
logger = get_logger("api.small.chemicals")


class ChemicalInsert(BaseModel):
    lagoon_id: str
    chemical: str
    amount: float
    unit: str
    metadata: dict[str, Any] = Field(default_factory=dict)


def _extract_user_id(user: dict) -> str:
    user_id = user.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return user_id


@router.get("/chemicals")
def list_chemicals(user: dict = Depends(require_roles(SMALL_READ_ROLES))):
    user_id = _extract_user_id(user)
    logger.info(
        "[API] endpoint_response_summary endpoint=/api/small/chemicals method=GET user_id=%s items_count=%s",
        user_id,
        0,
    )
    return {
        "product_type": "small",
        "items": [],
    }


@router.post("/chemicals")
def insert_chemical(
    payload: ChemicalInsert,
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
        lagoon_id=payload.lagoon_id,
        permission=PERMISSION_EDIT,
        expected_product_type=ProductType.SMALL,
    )
    logger.info(
        "[API] endpoint_response_summary endpoint=/api/small/chemicals method=POST user_id=%s lagoon_id=%s chemical=%s amount=%s",
        user_id,
        payload.lagoon_id,
        payload.chemical,
        payload.amount,
    )
    return {
        "ok": True,
        "product_type": "small",
        "lagoon_id": payload.lagoon_id,
        "chemical": payload.chemical,
        "amount": payload.amount,
        "unit": payload.unit,
        "requested_by": user_id,
    }


@router.delete("/chemicals")
def delete_chemical(
    lagoon_id: str,
    chemical: str,
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
        lagoon_id=lagoon_id,
        permission=PERMISSION_EDIT,
        expected_product_type=ProductType.SMALL,
    )
    logger.info(
        "[API] endpoint_response_summary endpoint=/api/small/chemicals method=DELETE user_id=%s lagoon_id=%s chemical=%s",
        user_id,
        lagoon_id,
        chemical,
    )
    return {
        "ok": True,
        "product_type": "small",
        "lagoon_id": lagoon_id,
        "chemical": chemical,
        "deleted_by": user_id,
    }
