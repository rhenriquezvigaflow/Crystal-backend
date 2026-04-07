from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.security.rbac import CRYSTAL_READ_ROLES, CRYSTAL_WRITE_ROLES, require_roles

router = APIRouter(prefix="/api/crystal", tags=["Crystal Tags"])
logger = get_logger("api.crystal.tags")


class TagsUpdate(BaseModel):
    tags: dict[str, Any] = Field(default_factory=dict)


@router.get("/tags")
def get_tags(_user: dict = Depends(require_roles(CRYSTAL_READ_ROLES))):
    logger.info(
        "[API] endpoint_response_summary endpoint=/api/crystal/tags method=GET user_id=%s",
        _user.get("sub"),
    )
    return {
        "product_type": "crystal",
        "tags": {},
    }


@router.put("/tags")
def update_tags(
    payload: TagsUpdate,
    user: dict = Depends(require_roles(CRYSTAL_WRITE_ROLES)),
):
    logger.info(
        "[API] endpoint_response_summary endpoint=/api/crystal/tags method=PUT user_id=%s tags_count=%s",
        user.get("sub"),
        len(payload.tags),
    )
    return {
        "ok": True,
        "product_type": "crystal",
        "updated_by": user.get("sub"),
        "count": len(payload.tags),
    }


@router.delete("/tags")
def delete_tags(user: dict = Depends(require_roles(CRYSTAL_WRITE_ROLES))):
    logger.info(
        "[API] endpoint_response_summary endpoint=/api/crystal/tags method=DELETE user_id=%s",
        user.get("sub"),
    )
    return {
        "ok": True,
        "product_type": "crystal",
        "deleted_by": user.get("sub"),
    }
