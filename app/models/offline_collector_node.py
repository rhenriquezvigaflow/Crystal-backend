from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OfflineCollectorNode(Base):
    __tablename__ = "offline_collector_node"

    source_node_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    lagoon_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("lagoons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
