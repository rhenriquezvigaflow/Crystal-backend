from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models.base import Base

ALARM_TYPE_THRESHOLD = "threshold"
ALARM_TYPE_STATE = "state"
ALARM_TYPE_COMM_LOSS = "comm_loss"


class AlarmDefinition(Base):
    __tablename__ = "alarm_definition"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    lagoon_id = Column(
        String(64),
        ForeignKey("lagoons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    tag_id = Column(
        String(128),
        nullable=True,
        index=True,
    )

    code = Column(
        String(128),
        nullable=False,
    )

    name = Column(
        String(255),
        nullable=False,
    )

    description = Column(
        Text,
        nullable=True,
    )

    alarm_type = Column(
        String(32),
        nullable=False,
        index=True,
    )

    severity = Column(
        String(32),
        nullable=False,
        server_default=text("'warning'"),
    )

    enabled = Column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    condition = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    deadband = Column(
        Float,
        nullable=False,
        server_default=text("0"),
    )

    last_seen_ts = Column(
        DateTime(timezone=True),
        nullable=True,
    )

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
            "code",
            name="uq_alarm_definition_lagoon_code",
        ),
        CheckConstraint(
            "alarm_type IN ('threshold', 'state', 'comm_loss')",
            name="ck_alarm_definition_alarm_type",
        ),
        Index(
            "ix_alarm_definition_lagoon_enabled_type_tag",
            "lagoon_id",
            "enabled",
            "alarm_type",
            "tag_id",
        ),
    )


class AlarmEvent(Base):
    __tablename__ = "alarm_event"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    alarm_definition_id = Column(
        UUID(as_uuid=True),
        ForeignKey("alarm_definition.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    lagoon_id = Column(
        String(64),
        nullable=False,
        index=True,
    )

    tag_id = Column(
        String(128),
        nullable=True,
        index=True,
    )

    alarm_type = Column(
        String(32),
        nullable=False,
        index=True,
    )

    severity = Column(
        String(32),
        nullable=False,
        index=True,
    )

    status = Column(
        String(16),
        nullable=False,
        server_default=text("'OPEN'"),
        index=True,
    )

    open_reason = Column(
        Text,
        nullable=True,
    )

    close_reason = Column(
        Text,
        nullable=True,
    )

    open_value = Column(
        Text,
        nullable=True,
    )

    close_value = Column(
        Text,
        nullable=True,
    )

    opened_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    closed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    duration_sec = Column(
        Integer,
        nullable=True,
    )

    source_ts = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    last_eval_ts = Column(
        DateTime(timezone=True),
        nullable=True,
    )

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
        CheckConstraint(
            "status IN ('OPEN', 'CLOSED')",
            name="ck_alarm_event_status",
        ),
        Index(
            "uq_alarm_event_open_per_definition",
            "alarm_definition_id",
            unique=True,
            postgresql_where=text("status = 'OPEN'"),
        ),
        Index(
            "ix_alarm_event_lagoon_status_opened_at",
            "lagoon_id",
            "status",
            "opened_at",
        ),
    )


class AlarmNotificationRule(Base):
    __tablename__ = "alarm_notification_rule"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    enabled = Column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    scope = Column(
        String(32),
        nullable=False,
        server_default=text("'global'"),
        index=True,
    )

    lagoon_id = Column(
        String(64),
        ForeignKey("lagoons.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    alarm_definition_id = Column(
        UUID(as_uuid=True),
        ForeignKey("alarm_definition.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    alarm_type = Column(
        String(32),
        nullable=True,
        index=True,
    )

    severity = Column(
        String(32),
        nullable=True,
        index=True,
    )

    tag_pattern = Column(
        String(128),
        nullable=True,
    )

    channel = Column(
        String(32),
        nullable=False,
        index=True,
    )

    target = Column(
        String(255),
        nullable=False,
    )

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
        CheckConstraint(
            "scope IN ('global', 'lagoon', 'definition')",
            name="ck_alarm_notification_rule_scope",
        ),
        Index(
            "ix_alarm_notification_routing",
            "enabled",
            "lagoon_id",
            "alarm_definition_id",
            "alarm_type",
            "severity",
        ),
    )
