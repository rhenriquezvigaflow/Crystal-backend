from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Enum as SQLEnum, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.user_role import UserRole


class ProductType(str, Enum):
    CRYSTAL = "crystal"
    SMALL = "small"


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint(
            "name",
            "product_type",
            name="uq_roles_name_product_type",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    product_type: Mapped[ProductType] = mapped_column(
        SQLEnum(
            ProductType,
            name="product_type",
            # PostgreSQL enum labels are lowercase: crystal/small.
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    users: Mapped[list["User"]] = relationship(
        "User",
        secondary="user_roles",
        back_populates="roles",
        overlaps="user_roles,user,role",
    )
    user_roles: Mapped[list["UserRole"]] = relationship(
        "UserRole",
        back_populates="role",
        cascade="all, delete-orphan",
        overlaps="users,roles",
    )
