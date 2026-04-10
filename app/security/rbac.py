from __future__ import annotations

from typing import Iterable

from fastapi import (
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketException,
    status,
)
from sqlalchemy.orm import Session

from app.auth.jwt import decode_access_token, get_current_user, get_token_roles
from app.auth.services.lagoon_service import (
    PERMISSION_VIEW,
    VALID_PERMISSIONS,
    get_lagoon_by_id,
    resolve_permitted_product_types,
    user_has_any_permission,
    user_has_permission,
)
from app.db.session import SessionLocal, get_db
from app.models.role import ProductType
from app.core.logging import get_logger

logger = get_logger("security.rbac")

ROLE_ADMIN_CRYSTAL = "AdminCrystal"
ROLE_VISUAL_CRYSTAL = "VisualCrystal"
ROLE_ADMIN_SMALL = "AdminSmall"
ROLE_VISUAL_SMALL = "VisualSmall"
ROLE_SUPERADMIN = "SuperAdmin"

CRYSTAL_READ_ROLES = [ROLE_ADMIN_CRYSTAL, ROLE_VISUAL_CRYSTAL, ROLE_SUPERADMIN]
CRYSTAL_WRITE_ROLES = [ROLE_ADMIN_CRYSTAL]
SMALL_READ_ROLES = [ROLE_ADMIN_SMALL, ROLE_VISUAL_SMALL, ROLE_SUPERADMIN]
SMALL_WRITE_ROLES = [ROLE_ADMIN_SMALL]

ALL_READ_ROLES = [
    ROLE_ADMIN_CRYSTAL,
    ROLE_VISUAL_CRYSTAL,
    ROLE_ADMIN_SMALL,
    ROLE_VISUAL_SMALL,
    ROLE_SUPERADMIN,
]


def _extract_user_id(user_payload: dict) -> str:
    subject = user_payload.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return subject


def _normalize_roles(values: Iterable[object]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for value in values:
        if not isinstance(value, str):
            continue
        role = value.strip()
        if not role or role in seen:
            continue
        seen.add(role)
        normalized.append(role)

    return normalized


def extract_user_roles(user_payload: dict) -> list[str]:
    if not isinstance(user_payload, dict):
        return []

    roles = get_token_roles(user_payload)
    if roles:
        return roles

    legacy = user_payload.get("role")
    if isinstance(legacy, str):
        return _normalize_roles([legacy])

    return []


def has_superadmin_role(user_payload: dict) -> bool:
    user_roles = {
        role.lower()
        for role in extract_user_roles(user_payload)
    }
    return ROLE_SUPERADMIN.lower() in user_roles


def _ensure_allowed_roles(
    user_payload: dict,
    allowed_roles: list[str],
    error_detail: str = "Forbidden",
) -> dict:
    user_roles = set(extract_user_roles(user_payload))
    user_roles_lower = {role.lower() for role in user_roles}
    required = {role.lower() for role in allowed_roles if role}

    if required and not user_roles_lower.intersection(required):
        raise HTTPException(status_code=403, detail=error_detail)

    user_payload["roles"] = sorted(user_roles)
    return user_payload


def require_roles(roles: list[str]):
    def checker(user: dict = Depends(get_current_user)) -> dict:
        return _ensure_allowed_roles(
            user_payload=user,
            allowed_roles=roles,
        )

    return checker


def require_permission(
    permission: str,
    lagoon_id_param: str | None = "lagoon_id",
):
    if permission not in VALID_PERMISSIONS:
        raise ValueError(f"Unsupported permission: {permission}")

    def checker(
        request: Request,
        db: Session = Depends(get_db),
        user: dict = Depends(get_current_user),
    ) -> dict:
        user_id = _extract_user_id(user)

        lagoon_id: str | None = None
        if lagoon_id_param:
            path_value = request.path_params.get(lagoon_id_param)
            query_value = request.query_params.get(lagoon_id_param)
            candidate = path_value or query_value
            if isinstance(candidate, str) and candidate.strip():
                lagoon_id = candidate.strip()

        if lagoon_id:
            allowed = user_has_permission(
                db=db,
                user_id=user_id,
                lagoon_id=lagoon_id,
                permission=permission,
            )
        else:
            allowed = user_has_any_permission(
                db=db,
                user_id=user_id,
                permission=permission,
            )

        if not allowed:
            raise HTTPException(status_code=403, detail="Forbidden")

        return user

    return checker


def _extract_ws_token(websocket: WebSocket, token: str | None) -> str:
    if token:
        if token.lower().startswith("bearer "):
            return token.split(" ", 1)[1].strip()
        return token.strip()

    authorization = websocket.headers.get("authorization")
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()

    raise WebSocketException(
        code=status.WS_1008_POLICY_VIOLATION,
        reason="Missing token",
    )


def ensure_websocket_roles(
    websocket: WebSocket,
    roles: list[str],
    token: str | None = None,
) -> dict:
    raw_token = _extract_ws_token(websocket, token=token)

    try:
        user = decode_access_token(raw_token)
    except HTTPException as exc:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason=exc.detail,
        )

    user_roles = set(extract_user_roles(user))
    required = {role for role in roles if role}

    if required and not user_roles.intersection(required):
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Forbidden",
        )

    user["roles"] = sorted(user_roles)
    return user


def ensure_websocket_permission(
    websocket: WebSocket,
    lagoon_id: str,
    permission: str = PERMISSION_VIEW,
    token: str | None = None,
) -> dict:
    if permission not in VALID_PERMISSIONS:
        raise ValueError(f"Unsupported permission: {permission}")

    raw_token = _extract_ws_token(websocket, token=token)

    try:
        user = decode_access_token(raw_token)
    except HTTPException as exc:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason=exc.detail,
        )

    user_id = user.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid token payload",
        )

    user_roles = extract_user_roles(user)
    permitted_products = sorted(resolve_permitted_product_types(user_roles))
    email = str(user.get("email", "-"))

    db = SessionLocal()
    try:
        allowed = user_has_permission(
            db=db,
            user_id=user_id,
            lagoon_id=lagoon_id,
            permission=permission,
        )
        access_mode = "fine_grained" if allowed else "none"
        lagoon_product = "-"

        if not allowed and permitted_products:
            lagoon = get_lagoon_by_id(db=db, lagoon_id=lagoon_id)
            if lagoon is not None:
                raw_product = lagoon.product_type
                lagoon_product = (
                    raw_product.value
                    if isinstance(raw_product, ProductType)
                    else str(raw_product)
                )
                if lagoon_product in permitted_products:
                    allowed = True
                    access_mode = "product_admin"
    finally:
        db.close()

    if not allowed:
        logger.warning(
            "[RBAC][WS] denied user_id=%s email=%s lagoon_id=%s permission=%s roles=%s permitted_products=%s",
            user_id,
            email,
            lagoon_id,
            permission,
            sorted(set(user_roles)),
            permitted_products,
        )
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Forbidden",
        )

    logger.info(
        "[RBAC][WS] user_scope_resolved user_id=%s email=%s lagoon_id=%s lagoon_product=%s permission=%s mode=%s roles=%s permitted_products=%s",
        user_id,
        email,
        lagoon_id,
        lagoon_product,
        permission,
        access_mode,
        sorted(set(user_roles)),
        permitted_products,
    )
    return user
