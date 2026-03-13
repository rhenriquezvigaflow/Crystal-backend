import unittest

from fastapi import HTTPException

from app.security.rbac import (
    ROLE_ADMIN_CRYSTAL,
    ROLE_VISUAL_SMALL,
    extract_user_roles,
    require_roles,
)


class TestRbac(unittest.TestCase):
    def test_require_roles_allows_matching_role(self):
        checker = require_roles([ROLE_ADMIN_CRYSTAL])
        user = checker(user={"sub": "1", "roles": [ROLE_ADMIN_CRYSTAL]})
        self.assertEqual(user["sub"], "1")
        self.assertEqual(user["roles"], [ROLE_ADMIN_CRYSTAL])

    def test_require_roles_rejects_non_matching_role(self):
        checker = require_roles([ROLE_ADMIN_CRYSTAL])
        with self.assertRaises(HTTPException) as ctx:
            checker(user={"sub": "1", "roles": [ROLE_VISUAL_SMALL]})

        self.assertEqual(ctx.exception.status_code, 403)

    def test_extract_user_roles_supports_legacy_role_claim(self):
        roles = extract_user_roles({"sub": "1", "role": ROLE_ADMIN_CRYSTAL})
        self.assertEqual(roles, [ROLE_ADMIN_CRYSTAL])


if __name__ == "__main__":
    unittest.main()
