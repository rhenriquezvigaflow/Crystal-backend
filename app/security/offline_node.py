from __future__ import annotations

from hashlib import sha256
from hmac import compare_digest

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.offline_collector_node import OfflineCollectorNode


def extract_bearer_token(authorization: str | None) -> str:
    scheme, separator, token = (authorization or "").partition(" ")
    if not separator or scheme.lower() != "bearer" or len(token.strip()) < 24:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid offline node token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token.strip()


def authenticate_offline_node(db: Session, authorization: str | None) -> OfflineCollectorNode:
    token = extract_bearer_token(authorization)
    token_hash = sha256(token.encode("utf-8")).hexdigest()
    node = (
        db.query(OfflineCollectorNode)
        .filter(
            OfflineCollectorNode.token_hash == token_hash,
            OfflineCollectorNode.enabled.is_(True),
        )
        .first()
    )
    if node is None or not compare_digest(node.token_hash, token_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid offline node token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return node
