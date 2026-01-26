from sqlalchemy import (
    Column,
    DateTime,
    String,
    ForeignKey,
    Index,
    func,
)
from app.models.base import Base


class ScadaEvent(Base):
    __tablename__ = "scada_event"

    id = Column(
        String,
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    lagoon_id = Column(
        String(64),
        ForeignKey("lagoons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    tag_id = Column(String(64), nullable=False, index=True)
    tag_label = Column(String(128))

    start_ts = Column(DateTime(timezone=True), nullable=False)
    end_ts = Column(DateTime(timezone=True))

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "ix_scada_event_open",
            "lagoon_id",
            "tag_id",
            postgresql_where=(end_ts.is_(None)),
        ),
    )
