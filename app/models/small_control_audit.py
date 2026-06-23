from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SmallControlAudit(Base):
    __tablename__ = "small_control_audit"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    lagoon_id: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    module_id: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    control_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(150), nullable=False)
    command_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    tag_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    node_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    previous_value: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    change_summary: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        index=True,
    )
    error_detail: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    user_id: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    user_email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
