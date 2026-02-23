from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import settings

SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM

security = HTTPBearer(auto_error=False)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )
        if "sub" not in payload:
            raise HTTPException(
                status_code=401,
                detail="Invalid token payload",
            )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )


def get_current_user(
    token: HTTPAuthorizationCredentials = Depends(security),
):
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing bearer token",
        )
    return decode_access_token(token.credentials)
