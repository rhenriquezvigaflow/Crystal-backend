from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Identity, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class LagoonLayoutMapping(Base):
    __tablename__ = "lagoon_layout_mapping"

    id: Mapped[int] = mapped_column(
        Identity(start=1),
        primary_key=True,
    )
    lagoon_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("lagoons.id", ondelete="CASCADE"),
        nullable=False,
    )
    layout_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("layouts.id", ondelete="CASCADE"),
        nullable=False,
    )
    mapping_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "lagoon_id",
            "layout_id",
            name="uq_lagoon_layout_mapping_lagoon_layout",
        ),
        Index(
            "ix_lagoon_layout_mapping_lagoon_id",
            "lagoon_id",
        ),
        Index(
            "ix_lagoon_layout_mapping_layout_id",
            "layout_id",
        ),
    )
