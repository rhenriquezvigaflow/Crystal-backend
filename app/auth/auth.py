from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.auth.jwt import create_token
from app.auth.password import hash_password as _hash_password
from app.auth.services.auth_service import authenticate_user, build_login_response
from app.core.logging import get_logger
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = get_logger("auth.login")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginUser(BaseModel):
    id: str
    email: EmailStr
    roles: list[str]
    role: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: LoginUser


# Backward compatibility with previous naming.
LoginPayload = LoginRequest


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    return create_token(data, expires_delta=expires_delta)


def hash_password(password: str) -> str:
    return _hash_password(password)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = authenticate_user(
        db=db,
        email=str(payload.email),
        password=payload.password,
    )
    response = build_login_response(user)
    client_ip = request.client.host if request.client else "-"
    logger.info(
        "[LOGIN OK] user_id=%s email=%s roles=%s ip=%s",
        response["user"]["id"],
        response["user"]["email"],
        response["user"]["roles"],
        client_ip,
    )
    return response
