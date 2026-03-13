from enum import Enum

from app.models.role import ProductType, Role as RBACRole
from app.models.user import User
from app.models.user_role import UserRole


class Role(str, Enum):
    ADMIN = "ADMIN"
    USER = "USER"


__all__ = [
    "User",
    "UserRole",
    "RBACRole",
    "ProductType",
    "Role",
]
