from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.logging import get_logger
from app.models.auth_2fa_challenge import Auth2FAChallenge
from app.models.user import User
from app.services.email_service import EmailConfigurationError, EmailService

TWO_FACTOR_CODE_DIGITS = 4
TWO_FACTOR_TTL_MINUTES = 10
TWO_FACTOR_MAX_ATTEMPTS = 5
TWO_FACTOR_MESSAGE = "Introduzca el numero de 4 digitos"

logger = get_logger("auth.2fa")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _generate_code() -> str:
    return f"{secrets.randbelow(10 ** TWO_FACTOR_CODE_DIGITS):0{TWO_FACTOR_CODE_DIGITS}d}"


def _normalize_code(code: str) -> str:
    return "".join(char for char in str(code or "").strip() if char.isdigit())


def _hash_code(challenge_id: uuid.UUID, code: str) -> str:
    message = f"{challenge_id}:{code}".encode("utf-8")
    secret = settings.JWT_SECRET_KEY.encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def _verify_code(challenge: Auth2FAChallenge, code: str) -> bool:
    expected_hash = _hash_code(challenge.id, code)
    return hmac.compare_digest(challenge.code_hash, expected_hash)


def _load_user(db: Session, user_id: int) -> User | None:
    query = db.query(User)
    if hasattr(query, "options"):
        query = query.options(joinedload(User.roles))
    return query.filter(User.id == user_id).first()


def _consume_challenge(db: Session, challenge: Auth2FAChallenge, now: datetime) -> None:
    challenge.consumed_at = now
    db.add(challenge)
    db.commit()


def create_2fa_challenge(
    *,
    db: Session,
    user: User,
    email_service: EmailService,
) -> Auth2FAChallenge:
    now = _now_utc()
    code = _generate_code()
    challenge_id = uuid.uuid4()

    db.query(Auth2FAChallenge).filter(
        Auth2FAChallenge.user_id == user.id,
        Auth2FAChallenge.consumed_at.is_(None),
    ).update(
        {Auth2FAChallenge.consumed_at: now},
        synchronize_session=False,
    )

    challenge = Auth2FAChallenge(
        id=challenge_id,
        user_id=user.id,
        code_hash=_hash_code(challenge_id, code),
        expires_at=now + timedelta(minutes=TWO_FACTOR_TTL_MINUTES),
        attempts=0,
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)

    try:
        email_service.send_auth_2fa_code_sync(
            recipient=user.email,
            code=code,
            expires_minutes=TWO_FACTOR_TTL_MINUTES,
        )
    except EmailConfigurationError as exc:
        _consume_challenge(db, challenge, _now_utc())
        logger.error(
            "[2FA EMAIL ERROR] user_id=%s challenge_id=%s reason=not_configured",
            user.id,
            challenge.id,
        )
        raise HTTPException(
            status_code=503,
            detail="2FA email service is not configured",
        ) from exc
    except Exception as exc:
        _consume_challenge(db, challenge, _now_utc())
        logger.exception(
            "[2FA EMAIL ERROR] user_id=%s challenge_id=%s reason=send_failed",
            user.id,
            challenge.id,
        )
        raise HTTPException(
            status_code=503,
            detail="Could not send 2FA code",
        ) from exc

    logger.info(
        "[2FA CHALLENGE CREATED] user_id=%s challenge_id=%s expires_at=%s",
        user.id,
        challenge.id,
        challenge.expires_at.isoformat(),
    )
    return challenge


def verify_2fa_challenge(
    *,
    db: Session,
    challenge_id: uuid.UUID,
    code: str,
) -> User:
    challenge = (
        db.query(Auth2FAChallenge)
        .filter(Auth2FAChallenge.id == challenge_id)
        .first()
    )
    if challenge is None:
        logger.warning("[2FA VERIFY FAIL] challenge_id=%s reason=not_found", challenge_id)
        raise HTTPException(status_code=400, detail="Invalid 2FA challenge")

    now = _now_utc()
    if challenge.consumed_at is not None:
        logger.warning(
            "[2FA VERIFY FAIL] user_id=%s challenge_id=%s reason=consumed",
            challenge.user_id,
            challenge.id,
        )
        raise HTTPException(status_code=400, detail="2FA challenge already used")

    if challenge.expires_at <= now:
        _consume_challenge(db, challenge, now)
        logger.warning(
            "[2FA VERIFY FAIL] user_id=%s challenge_id=%s reason=expired",
            challenge.user_id,
            challenge.id,
        )
        raise HTTPException(status_code=400, detail="2FA code expired")

    if challenge.attempts >= TWO_FACTOR_MAX_ATTEMPTS:
        _consume_challenge(db, challenge, now)
        logger.warning(
            "[2FA VERIFY FAIL] user_id=%s challenge_id=%s reason=max_attempts",
            challenge.user_id,
            challenge.id,
        )
        raise HTTPException(status_code=429, detail="Too many 2FA attempts")

    normalized_code = _normalize_code(code)
    if (
        len(normalized_code) != TWO_FACTOR_CODE_DIGITS
        or not _verify_code(challenge, normalized_code)
    ):
        challenge.attempts += 1
        if challenge.attempts >= TWO_FACTOR_MAX_ATTEMPTS:
            challenge.consumed_at = now
        db.add(challenge)
        db.commit()
        logger.warning(
            "[2FA VERIFY FAIL] user_id=%s challenge_id=%s attempts=%s reason=invalid_code",
            challenge.user_id,
            challenge.id,
            challenge.attempts,
        )
        raise HTTPException(status_code=401, detail="Invalid 2FA code")

    user = _load_user(db, challenge.user_id)
    if user is None or not user.is_active:
        _consume_challenge(db, challenge, now)
        logger.warning(
            "[2FA VERIFY FAIL] user_id=%s challenge_id=%s reason=user_unavailable",
            challenge.user_id,
            challenge.id,
        )
        raise HTTPException(status_code=403, detail="Access not allowed")

    challenge.consumed_at = now
    db.add(challenge)
    db.commit()
    logger.info(
        "[2FA VERIFY OK] user_id=%s challenge_id=%s attempts=%s",
        challenge.user_id,
        challenge.id,
        challenge.attempts,
    )
    return user
