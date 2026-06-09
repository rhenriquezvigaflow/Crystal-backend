from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.auth.jwt import ACCESS_TOKEN_EXPIRE_MINUTES, create_token
from app.auth.password import verify_password
from app.core.logging import get_logger
from app.models.role import ProductType
from app.models.user import User

logger = get_logger("auth.login")

MAX_FINAL_TOKEN_EXPIRE_MINUTES = 24 * 60
SMALL_ROLE_NAMES = {"AdminSmall", "VisualSmall"}
CRYSTAL_ROLE_NAMES = {"AdminCrystal", "VisualCrystal"}


def _normalize_roles(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for value in values:
        role = value.strip()
        if not role or role in seen:
            continue
        seen.add(role)
        normalized.append(role)

    return normalized


def extract_user_roles(user: object) -> list[str]:
    role_names: list[str] = []

    rel_roles = getattr(user, "roles", None)
    if isinstance(rel_roles, list):
        role_names.extend(
            role.name
            for role in rel_roles
            if isinstance(getattr(role, "name", None), str)
        )

    legacy_role = getattr(user, "role", None)
    if isinstance(legacy_role, str):
        role_names.append(legacy_role)

    return _normalize_roles(role_names)


def _normalize_product_type(value: object) -> str | None:
    if isinstance(value, ProductType):
        return value.value
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in {ProductType.CRYSTAL.value, ProductType.SMALL.value}:
            return cleaned
    return None


def extract_user_product_types(user: object) -> list[str]:
    product_types: list[str] = []
    seen: set[str] = set()

    def push(value: str | None) -> None:
        if not value or value in seen:
            return
        seen.add(value)
        product_types.append(value)

    rel_roles = getattr(user, "roles", None)
    if isinstance(rel_roles, list):
        for role in rel_roles:
            product_type = _normalize_product_type(getattr(role, "product_type", None))
            if product_type is None:
                role_name = getattr(role, "name", None)
                if role_name in SMALL_ROLE_NAMES:
                    product_type = ProductType.SMALL.value
                elif role_name in CRYSTAL_ROLE_NAMES:
                    product_type = ProductType.CRYSTAL.value
            push(product_type)

    return product_types


def user_requires_small_2fa(user: object) -> bool:
    product_types = extract_user_product_types(user)
    if ProductType.SMALL.value in product_types:
        return True

    return any(role in SMALL_ROLE_NAMES for role in extract_user_roles(user))


def _primary_product_type(product_types: list[str]) -> str | None:
    if ProductType.SMALL.value in product_types:
        return ProductType.SMALL.value
    if ProductType.CRYSTAL.value in product_types:
        return ProductType.CRYSTAL.value
    return product_types[0] if product_types else None


def _effective_token_expiry(expires_delta: timedelta | None = None) -> timedelta:
    if expires_delta is not None:
        max_delta = timedelta(minutes=MAX_FINAL_TOKEN_EXPIRE_MINUTES)
        return min(expires_delta, max_delta)

    minutes = max(1, min(ACCESS_TOKEN_EXPIRE_MINUTES, MAX_FINAL_TOKEN_EXPIRE_MINUTES))
    return timedelta(minutes=minutes)


def authenticate_user(db: Session, email: str, password: str) -> User:
    query = db.query(User)
    if hasattr(query, "options"):
        query = query.options(joinedload(User.roles))

    user = query.filter(User.email == email).first()
    if not user:
        logger.warning("[LOGIN FAIL] email=%s reason=user_not_found", email)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        logger.warning(
            "[LOGIN FAIL] email=%s user_id=%s reason=user_disabled",
            email,
            user.id,
        )
        raise HTTPException(status_code=403, detail="User disabled")

    if not verify_password(password, user.password_hash):
        logger.warning(
            "[LOGIN FAIL] email=%s user_id=%s reason=invalid_password",
            email,
            user.id,
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return user


def build_login_response(
    user: User,
    *,
    auth_level: str = "password",
    expires_delta: timedelta | None = None,
) -> dict[str, Any]:
    user_roles = extract_user_roles(user)
    if not user_roles:
        logger.warning(
            "[LOGIN FAIL] email=%s user_id=%s reason=no_roles_assigned",
            user.email,
            user.id,
        )
        raise HTTPException(status_code=403, detail="User has no assigned roles")

    primary_role = user_roles[0]
    product_types = extract_user_product_types(user)
    product_type = _primary_product_type(product_types)
    token_expiry = _effective_token_expiry(expires_delta)
    token_payload = {
        "sub": str(user.id),
        "email": user.email,
        # Claims below are kept for backward compatibility with existing role checks.
        "roles": user_roles,
        "role": primary_role,
        "product_type": product_type,
        "product_types": product_types,
        "auth_level": auth_level,
    }
    token = create_token(token_payload, expires_delta=token_expiry)

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": int(token_expiry.total_seconds()),
        "user": {
            "id": str(user.id),
            "email": user.email,
            "roles": user_roles,
            "role": primary_role,
            "product_type": product_type,
            "product_types": product_types,
            "auth_level": auth_level,
        },
    }
