from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.security.rbac import CRYSTAL_READ_ROLES, CRYSTAL_WRITE_ROLES, require_roles

router = APIRouter(prefix="/api/crystal", tags=["Crystal Layout"])
logger = get_logger("api.crystal.layout")


class LayoutUpdate(BaseModel):
    layout_id: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


@router.get("/layout")
def get_layout(_user: dict = Depends(require_roles(CRYSTAL_READ_ROLES))):
    logger.info(
        "[API] endpoint_response_summary endpoint=/api/crystal/layout method=GET user_id=%s",
        _user.get("sub"),
    )
    return {
        "product_type": "crystal",
        "layout": {},
    }


@router.put("/layout")
def update_layout(
    payload: LayoutUpdate,
    user: dict = Depends(require_roles(CRYSTAL_WRITE_ROLES)),
):
    logger.info(
        "[API] endpoint_response_summary endpoint=/api/crystal/layout method=PUT user_id=%s layout_id=%s",
        user.get("sub"),
        payload.layout_id,
    )
    return {
        "ok": True,
        "product_type": "crystal",
        "updated_by": user.get("sub"),
        "layout_id": payload.layout_id,
    }


@router.delete("/layout")
def delete_layout(user: dict = Depends(require_roles(CRYSTAL_WRITE_ROLES))):
    logger.info(
        "[API] endpoint_response_summary endpoint=/api/crystal/layout method=DELETE user_id=%s",
        user.get("sub"),
    )
    return {
        "ok": True,
        "product_type": "crystal",
        "deleted_by": user.get("sub"),
    }
