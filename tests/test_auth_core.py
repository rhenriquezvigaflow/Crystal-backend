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
    def __init__(self, email: str, password_hash: str):
        self.id = uuid.uuid4()
        self.email = email
        self.password_hash = password_hash
        self.role = Role.USER.value
        self.is_active = True


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
            {"sub": "user-1", "role": Role.USER.value}
        )
        payload = decode_access_token(token)
        self.assertEqual(payload["sub"], "user-1")

    def test_expired_token_is_rejected(self):
        expired_token = create_access_token(
            {"sub": "user-1"},
            expires_delta=timedelta(seconds=-1),
        )
        with self.assertRaises(HTTPException):
            decode_access_token(expired_token)


if __name__ == "__main__":
    unittest.main()

