from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.security.rbac import SMALL_READ_ROLES, SMALL_WRITE_ROLES, require_roles

router = APIRouter(prefix="/api/small", tags=["Small Chemicals"])


class ChemicalInsert(BaseModel):
    lagoon_id: str
    chemical: str
    amount: float
    unit: str
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.get("/chemicals")
def list_chemicals(_user: dict = Depends(require_roles(SMALL_READ_ROLES))):
    return {
        "product_type": "small",
        "items": [],
    }


@router.post("/chemicals")
def insert_chemical(
    payload: ChemicalInsert,
    user: dict = Depends(require_roles(SMALL_WRITE_ROLES)),
):
    return {
        "ok": True,
        "product_type": "small",
        "lagoon_id": payload.lagoon_id,
        "chemical": payload.chemical,
        "amount": payload.amount,
        "unit": payload.unit,
        "requested_by": user.get("sub"),
    }


@router.delete("/chemicals")
def delete_chemical(
    lagoon_id: str,
    chemical: str,
    user: dict = Depends(require_roles(SMALL_WRITE_ROLES)),
):
    return {
        "ok": True,
        "product_type": "small",
        "lagoon_id": lagoon_id,
        "chemical": chemical,
        "deleted_by": user.get("sub"),
    }
