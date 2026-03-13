from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.security.rbac import CRYSTAL_READ_ROLES, CRYSTAL_WRITE_ROLES, require_roles

router = APIRouter(prefix="/api/crystal", tags=["Crystal Layout"])


class LayoutUpdate(BaseModel):
    layout_id: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


@router.get("/layout")
def get_layout(_user: dict = Depends(require_roles(CRYSTAL_READ_ROLES))):
    return {
        "product_type": "crystal",
        "layout": {},
    }


@router.put("/layout")
def update_layout(
    payload: LayoutUpdate,
    user: dict = Depends(require_roles(CRYSTAL_WRITE_ROLES)),
):
    return {
        "ok": True,
        "product_type": "crystal",
        "updated_by": user.get("sub"),
        "layout_id": payload.layout_id,
    }


@router.delete("/layout")
def delete_layout(user: dict = Depends(require_roles(CRYSTAL_WRITE_ROLES))):
    return {
        "ok": True,
        "product_type": "crystal",
        "deleted_by": user.get("sub"),
    }
