from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import settings

SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES

security = HTTPBearer(auto_error=False)


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


def get_token_roles(payload: dict) -> list[str]:
    roles_raw = payload.get("roles")
    roles: list[str] = []

    if isinstance(roles_raw, str):
        roles = _normalize_roles([roles_raw])
    elif isinstance(roles_raw, list):
        roles = _normalize_roles(roles_raw)

    # Backward compatibility for legacy single-role tokens.
    if not roles and isinstance(payload.get("role"), str):
        roles = _normalize_roles([payload["role"]])

    return roles


def create_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    return create_token(data, expires_delta=expires_delta)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if "sub" not in payload:
            raise HTTPException(status_code=401, detail="Invalid token payload")

        payload["roles"] = get_token_roles(payload)
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_current_user(
    token: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return decode_access_token(token.credentials)
