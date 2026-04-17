from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, EmailStr, Field, field_validator


def normalize_recipients(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, str):
        candidates = value.replace(";", ",").split(",")
    elif isinstance(value, list):
        candidates = value
    else:
        candidates = [value]

    recipients: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate is None:
            continue
        normalized = str(candidate).strip()
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        recipients.append(normalized)

    return recipients


class NotificationChannel(str, Enum):
    email = "email"
    webhook = "webhook"


class AlarmNotificationPayload(BaseModel):
    lagoon_id: str
    plant_name: str | None = None
    alarm_id: str
    alarm_code: str
    event_id: str
    timestamp: datetime
    priority: str
    category: str
    title: str
    description: str
    value_actual: str | None = None
    threshold: str | None = None
    recipients: list[EmailStr] = Field(default_factory=list)
    notification_channel: NotificationChannel = NotificationChannel.email
    level: str | None = None
    tag_id: str | None = None
    transition: str = "OPEN"
    reason: str | None = None

    @field_validator("recipients", mode="before")
    @classmethod
    def _normalize_recipients(cls, value: Any) -> list[str]:
        return normalize_recipients(value)

    @property
    def subject(self) -> str:
        level = (self.level or self.priority or "alert").upper()
        location = self.plant_name or self.lagoon_id
        return f"[{level}] {location} - {self.title}"


class NotificationJob(BaseModel):
    channel: str
    target: str
    transition: str
    alarm_type: str
    severity: str
    lagoon_id: str
    tag_id: str | None = None
    event_id: str
    happened_at: datetime
    message: str
    alarm_payload: AlarmNotificationPayload | None = None


class EmailTestAlertRequest(BaseModel):
    lagoon_id: str
    plant_name: str
    alarm_id: str = "manual-test"
    alarm_code: str = "manual_test"
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    priority: str = "warning"
    category: str = "manual"
    title: str
    description: str
    value_actual: str | None = None
    threshold: str | None = None
    recipients: list[EmailStr]
    level: str | None = None
    tag_id: str | None = None
    transition: str = "OPEN"
    reason: str | None = None

    @field_validator("recipients", mode="before")
    @classmethod
    def _normalize_recipients(cls, value: Any) -> list[str]:
        return normalize_recipients(value)

    def to_alarm_payload(self) -> AlarmNotificationPayload:
        return AlarmNotificationPayload(
            lagoon_id=self.lagoon_id,
            plant_name=self.plant_name,
            alarm_id=self.alarm_id,
            alarm_code=self.alarm_code,
            event_id=str(uuid4()),
            timestamp=self.timestamp,
            priority=self.priority,
            category=self.category,
            title=self.title,
            description=self.description,
            value_actual=self.value_actual,
            threshold=self.threshold,
            recipients=self.recipients,
            level=self.level,
            tag_id=self.tag_id,
            transition=self.transition,
            reason=self.reason,
        )
