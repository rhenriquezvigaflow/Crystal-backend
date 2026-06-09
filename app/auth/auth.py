from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.auth.jwt import create_token
from app.auth.password import hash_password as _hash_password
from app.auth.services.auth_service import (
    authenticate_user,
    build_login_response,
    user_requires_small_2fa,
)
from app.auth.services.two_factor_service import (
    TWO_FACTOR_MESSAGE,
    create_2fa_challenge,
    verify_2fa_challenge,
)
from app.core.logging import get_logger
from app.db.session import get_db
from app.services.email_service import EmailService

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
    product_type: str | None = None
    product_types: list[str] = Field(default_factory=list)
    auth_level: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: LoginUser


class TwoFactorRequiredResponse(BaseModel):
    requires_2fa: bool = True
    challenge_id: str
    message: str


class Verify2FARequest(BaseModel):
    challenge_id: UUID
    code: str


# Backward compatibility with previous naming.
LoginPayload = LoginRequest


def get_email_service() -> EmailService:
    return EmailService()


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    return create_token(data, expires_delta=expires_delta)


def hash_password(password: str) -> str:
    return _hash_password(password)


@router.post("/login", response_model=TokenResponse | TwoFactorRequiredResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
):
    user = authenticate_user(
        db=db,
        email=str(payload.email),
        password=payload.password,
    )
    client_ip = request.client.host if request.client else "-"

    if user_requires_small_2fa(user):
        challenge = create_2fa_challenge(
            db=db,
            user=user,
            email_service=email_service,
        )
        logger.info(
            "[LOGIN 2FA REQUIRED] user_id=%s email=%s challenge_id=%s ip=%s",
            user.id,
            user.email,
            challenge.id,
            client_ip,
        )
        return {
            "requires_2fa": True,
            "challenge_id": str(challenge.id),
            "message": TWO_FACTOR_MESSAGE,
        }

    response = build_login_response(user, auth_level="password")
    logger.info(
        "[LOGIN OK] user_id=%s email=%s roles=%s auth_level=password ip=%s",
        response["user"]["id"],
        response["user"]["email"],
        response["user"]["roles"],
        client_ip,
    )
    return response


@router.post("/verify-2fa", response_model=TokenResponse)
def verify_2fa(
    payload: Verify2FARequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = verify_2fa_challenge(
        db=db,
        challenge_id=payload.challenge_id,
        code=payload.code,
    )
    response = build_login_response(
        user,
        auth_level="2fa",
        expires_delta=timedelta(hours=24),
    )
    client_ip = request.client.host if request.client else "-"
    logger.info(
        "[LOGIN OK] user_id=%s email=%s roles=%s auth_level=2fa ip=%s",
        response["user"]["id"],
        response["user"]["email"],
        response["user"]["roles"],
        client_ip,
    )
    return response
