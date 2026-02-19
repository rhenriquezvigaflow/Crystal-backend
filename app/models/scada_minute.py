from sqlalchemy import (
    Column,
    DateTime,
    String,
    Text,
    Float,
    Boolean,
    ForeignKey,
    BigInteger,
    Integer,
    UniqueConstraint,
    Index,
    func,
    Date,                     # NUEVO
)

from app.models.base import Base


class ScadaMinute(Base):
    __tablename__ = "scada_minute"

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    lagoon_id = Column(
        String(64),
        ForeignKey("lagoons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    tag_id = Column(
        String(64),
        nullable=False,
        index=True,
    )

    # Timestamp truncado al minuto (UTC)
    bucket = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # =========================
    # Valores
    # =========================

    state = Column(
        Integer,
        nullable=True,
        index=True,
    )

    value_num = Column(
        Float,
        nullable=True,
    )

    value_bool = Column(
        Boolean,
        nullable=True,
    )

    # =========================
    # Timestamps
    # =========================

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "lagoon_id",
            "tag_id",
            "bucket",
            name="uq_scada_minute",
        ),
        Index(
            "ix_scada_minute_lagoon_bucket",
            "lagoon_id",
            "bucket",
        ),

    )
