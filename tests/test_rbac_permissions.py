import unittest
from unittest.mock import patch

from fastapi import HTTPException, WebSocketException

from app.auth.services.lagoon_service import PERMISSION_VIEW
from app.security.rbac import ensure_websocket_permission, require_permission


class _RequestStub:
    def __init__(self, path_params: dict | None = None, query_params: dict | None = None):
        self.path_params = path_params or {}
        self.query_params = query_params or {}


class _WebSocketStub:
    def __init__(self, token: str = "token"):
        self.headers = {"authorization": f"Bearer {token}"}


class _SessionStub:
    def close(self):
        return None


class TestRbacPermissions(unittest.TestCase):
    def test_require_permission_with_lagoon_path_param(self):
        checker = require_permission(PERMISSION_VIEW)
        request = _RequestStub(path_params={"lagoon_id": "lag-1"})

        with patch("app.security.rbac.user_has_permission", return_value=True):
            user = checker(
                request=request,
                db=object(),
                user={"sub": "user-1"},
            )

        self.assertEqual(user["sub"], "user-1")

    def test_require_permission_rejects_without_access(self):
        checker = require_permission(PERMISSION_VIEW)
        request = _RequestStub(path_params={"lagoon_id": "lag-1"})

        with patch("app.security.rbac.user_has_permission", return_value=False):
            with self.assertRaises(HTTPException) as ctx:
                checker(
                    request=request,
                    db=object(),
                    user={"sub": "user-1"},
                )

        self.assertEqual(ctx.exception.status_code, 403)

    def test_require_permission_without_lagoon_checks_any(self):
        checker = require_permission(PERMISSION_VIEW, lagoon_id_param=None)
        request = _RequestStub()

        with patch("app.security.rbac.user_has_any_permission", return_value=True):
            user = checker(
                request=request,
                db=object(),
                user={"sub": "user-1"},
            )

        self.assertEqual(user["sub"], "user-1")

    def test_ensure_websocket_permission_allows_authorized_user(self):
        websocket = _WebSocketStub()

        with patch(
            "app.security.rbac.decode_access_token",
            return_value={"sub": "user-1"},
        ), patch(
            "app.security.rbac.SessionLocal",
            return_value=_SessionStub(),
        ), patch(
            "app.security.rbac.user_has_permission",
            return_value=True,
        ):
            user = ensure_websocket_permission(
                websocket=websocket,
                lagoon_id="lag-1",
            )

        self.assertEqual(user["sub"], "user-1")

    def test_ensure_websocket_permission_rejects_unauthorized_user(self):
        websocket = _WebSocketStub()

        with patch(
            "app.security.rbac.decode_access_token",
            return_value={"sub": "user-1"},
        ), patch(
            "app.security.rbac.SessionLocal",
            return_value=_SessionStub(),
        ), patch(
            "app.security.rbac.user_has_permission",
            return_value=False,
        ):
            with self.assertRaises(WebSocketException) as ctx:
                ensure_websocket_permission(
                    websocket=websocket,
                    lagoon_id="lag-1",
                )

        self.assertEqual(ctx.exception.code, 1008)


if __name__ == "__main__":
    unittest.main()
