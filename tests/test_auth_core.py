import unittest
import uuid
from datetime import timedelta

from fastapi import HTTPException

from app.auth.auth import (
    LoginRequest,
    create_access_token,
    hash_password,
    login,
)
from app.auth.dependencies import decode_access_token
from app.auth.model import Role


class _QueryStub:
    def __init__(self, user):
        self._user = user

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._user


class _DBStub:
    def __init__(self, user):
        self._user = user

    def query(self, *args, **kwargs):
        return _QueryStub(self._user)


class _UserStub:
    def __init__(
        self,
        email: str,
        password_hash: str,
        role: str = Role.ADMIN.value,
        is_active: bool = True,
    ):
        self.id = uuid.uuid4()
        self.email = email
        self.password_hash = password_hash
        self.role = role
        self.is_active = is_active


class TestAuthCore(unittest.TestCase):
    def test_login_success_returns_token(self):
        email = "demo@example.com"
        raw_password = "Secret123!"
        user = _UserStub(email, hash_password(raw_password))
        db = _DBStub(user)

        response = login(
            payload=LoginRequest(email=email, password=raw_password),
            db=db,
        )

        self.assertIn("access_token", response)
        self.assertEqual(response["token_type"], "bearer")

    def test_token_decode_contains_subject(self):
        token = create_access_token(
            {"sub": "user-1", "role": Role.ADMIN.value}
        )
        payload = decode_access_token(token)
        self.assertEqual(payload["sub"], "user-1")

    def test_login_rejects_non_admin_role(self):
        email = "demo@example.com"
        raw_password = "Secret123!"
        user = _UserStub(
            email=email,
            password_hash=hash_password(raw_password),
            role=Role.USER.value,
        )
        db = _DBStub(user)

        with self.assertRaises(HTTPException) as ctx:
            login(payload=LoginRequest(email=email, password=raw_password), db=db)

        self.assertEqual(ctx.exception.status_code, 403)

    def test_expired_token_is_rejected(self):
        expired_token = create_access_token(
            {"sub": "user-1"},
            expires_delta=timedelta(seconds=-1),
        )
        with self.assertRaises(HTTPException):
            decode_access_token(expired_token)


if __name__ == "__main__":
    unittest.main()
