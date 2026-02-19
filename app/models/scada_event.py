from sqlalchemy import (
    Column,
    DateTime,
    String,
    Integer,
    ForeignKey,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base
import uuid


class ScadaEvent(Base):
    __tablename__ = "scada_event"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    lagoon_id = Column(
        String,
        nullable=True,
        index=True,
    )

    tag_id = Column(
        String,
        nullable=False,
        index=True,
    )

    tag_label = Column(
        String,
        nullable=True,
    )

    alert_type = Column(
        String,
        nullable=True,
        index=True,
    )

    state = Column(
        Integer,
        nullable=True,
    )

    previous_state = Column(
        Integer,
        nullable=True,
    )

    start_ts = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    end_ts = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    
    duration_sec = Column(
        Integer,
        nullable=True,
    )
