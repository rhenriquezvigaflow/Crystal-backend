from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.jwt import get_current_user
from app.auth.services.lagoon_service import (
    PERMISSION_EDIT,
    PERMISSION_VIEW,
    ensure_lagoon_access,
)
from app.core.logging import get_logger
from app.db.session import get_db
from app.layout_config.schemas import (
    LagoonLayoutMappingResponse,
    LayoutConfigUpdateRequest,
    LayoutResponse,
)
from app.layout_config.service import layout_config_service
from app.security.rbac import ALL_READ_ROLES, extract_user_roles, require_roles

router = APIRouter(tags=["SCADA Layouts"])
logger = get_logger("api.scada.layouts")


def _extract_user_id(user: dict) -> str:
    user_id = user.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return user_id


@router.get(
    "/layouts/{layout_id}",
    response_model=LayoutResponse,
)
def get_layout(
    layout_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles(ALL_READ_ROLES)),
):
    layout = layout_config_service.get_layout(
        db=db,
        layout_id=layout_id,
    )
    logger.info(
        "[API] endpoint_response_summary endpoint=/layouts/%s method=GET user_id=%s elements=%s",
        layout_id,
        user.get("sub"),
        len(layout.json_definition.elements),
    )
    return layout


@router.get(
    "/lagoons/{lagoon_id}/mapping",
    response_model=LagoonLayoutMappingResponse,
)
def get_lagoon_mapping(
    lagoon_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    lagoon = ensure_lagoon_access(
        db=db,
        user_id=_extract_user_id(user),
        user_email=str(user.get("email", "-")),
        user_roles=extract_user_roles(user),
        lagoon_id=lagoon_id,
        permission=PERMISSION_VIEW,
    )
    mapping = layout_config_service.get_lagoon_mapping(
        db=db,
        lagoon=lagoon,
    )
    logger.info(
        "[API] endpoint_response_summary endpoint=/lagoons/%s/mapping method=GET user_id=%s layout_id=%s mapped_elements=%s warnings=%s",
        lagoon_id,
        user.get("sub"),
        mapping.layout_id,
        len(mapping.mapping_json),
        len(mapping.warnings),
    )
    return mapping


@router.put(
    "/lagoons/{lagoon_id}/mapping",
    response_model=LagoonLayoutMappingResponse,
)
def update_lagoon_mapping(
    lagoon_id: str,
    payload: LayoutConfigUpdateRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    lagoon = ensure_lagoon_access(
        db=db,
        user_id=_extract_user_id(user),
        user_email=str(user.get("email", "-")),
        user_roles=extract_user_roles(user),
        lagoon_id=lagoon_id,
        permission=PERMISSION_EDIT,
    )

    try:
        config = layout_config_service.update_layout_config(
            db=db,
            lagoon=lagoon,
            layout_id=payload.layout_id,
            mapping_json=payload.mapping_json,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    logger.info(
        "[API] endpoint_response_summary endpoint=/lagoons/%s/mapping method=PUT user_id=%s layout_id=%s mapped_elements=%s",
        lagoon_id,
        user.get("sub"),
        config.mapping.layout_id,
        len(config.mapping.mapping_json),
    )
    return config.mapping
