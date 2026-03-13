from fastapi import Depends

from app.auth.jwt import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    create_token,
    decode_access_token,
    get_current_user,
    get_token_roles,
    security,
)
from app.auth.password import hash_password, verify_password
from app.security.rbac import ROLE_ADMIN_CRYSTAL, ROLE_ADMIN_SMALL, require_roles


def require_role(required_role: str):
    return require_roles([required_role])


def require_admin(
    user: dict = Depends(require_roles([ROLE_ADMIN_CRYSTAL, ROLE_ADMIN_SMALL])),
) -> dict:
    return user


__all__ = [
    "SECRET_KEY",
    "ALGORITHM",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "security",
    "hash_password",
    "verify_password",
    "create_token",
    "create_access_token",
    "decode_access_token",
    "get_token_roles",
    "get_current_user",
    "require_role",
    "require_admin",
]
