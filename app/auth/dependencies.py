from fastapi import Depends

from app.auth.jwt import decode_access_token, get_current_user
from app.security.rbac import ROLE_ADMIN_CRYSTAL, ROLE_ADMIN_SMALL, require_roles


def require_role(required_role: str):
    return require_roles([required_role])


def require_admin(
    user: dict = Depends(require_roles([ROLE_ADMIN_CRYSTAL, ROLE_ADMIN_SMALL])),
) -> dict:
    return user


__all__ = [
    "decode_access_token",
    "get_current_user",
    "require_role",
    "require_admin",
]
