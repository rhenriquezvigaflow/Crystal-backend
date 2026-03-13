from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.security.rbac import CRYSTAL_READ_ROLES, CRYSTAL_WRITE_ROLES, require_roles

router = APIRouter(prefix="/api/crystal", tags=["Crystal Tags"])


class TagsUpdate(BaseModel):
    tags: dict[str, Any] = Field(default_factory=dict)


@router.get("/tags")
def get_tags(_user: dict = Depends(require_roles(CRYSTAL_READ_ROLES))):
    return {
        "product_type": "crystal",
        "tags": {},
    }


@router.put("/tags")
def update_tags(
    payload: TagsUpdate,
    user: dict = Depends(require_roles(CRYSTAL_WRITE_ROLES)),
):
    return {
        "ok": True,
        "product_type": "crystal",
        "updated_by": user.get("sub"),
        "count": len(payload.tags),
    }


@router.delete("/tags")
def delete_tags(user: dict = Depends(require_roles(CRYSTAL_WRITE_ROLES))):
    return {
        "ok": True,
        "product_type": "crystal",
        "deleted_by": user.get("sub"),
    }
