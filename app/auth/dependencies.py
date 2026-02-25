from fastapi import Depends, HTTPException

from app.auth.model import Role
from app.auth.security import decode_access_token, get_current_user


def require_role(required_role: str):
    def checker(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") != required_role:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user

    return checker


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != Role.ADMIN.value:
        raise HTTPException(status_code=403, detail="ADMIN role required")
    return user
