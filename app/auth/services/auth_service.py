from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.auth.jwt import ACCESS_TOKEN_EXPIRE_MINUTES, create_token
from app.auth.password import verify_password
from app.models.user import User


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


def authenticate_user(db: Session, email: str, password: str) -> User:
    query = db.query(User)
    if hasattr(query, "options"):
        query = query.options(joinedload(User.roles))

    user = query.filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User disabled")

    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return user


def build_login_response(user: User) -> dict[str, Any]:
    user_roles = extract_user_roles(user)
    if not user_roles:
        raise HTTPException(status_code=403, detail="User has no assigned roles")

    primary_role = user_roles[0]
    token_payload = {
        "sub": str(user.id),
        "email": user.email,
        # Claims below are kept for backward compatibility with existing role checks.
        "roles": user_roles,
        "role": primary_role,
    }
    token = create_token(token_payload)

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "roles": user_roles,
            "role": primary_role,
        },
    }
