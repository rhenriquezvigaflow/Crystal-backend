from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.integration.notifications import NotificationOrchestrator
from app.schemas.notifications import AlarmNotificationPayload
from app.services.email_service import EmailService


class _DummyMailClient:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.messages = []

    async def send_message(self, message) -> None:
        if self.should_fail:
            raise RuntimeError("smtp down")
        self.messages.append(message)


def _build_settings():
    return SimpleNamespace(
        MAIL_USERNAME="mail-user",
        MAIL_PASSWORD="mail-pass",
        MAIL_FROM="alerts@example.com",
        MAIL_PORT=587,
        MAIL_SERVER="smtp.example.com",
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
        MAIL_FROM_NAME="Crystal SCADA",
        MAIL_TIMEOUT_SEC=15,
        MAIL_DISPATCH_MAX_WORKERS=1,
        email_templates_dir=Path("c:/WebCrystalScada/crystal-backend/app/templates/email"),
        is_mail_configured=True,
    )


def _build_payload() -> AlarmNotificationPayload:
    return AlarmNotificationPayload(
        lagoon_id="kirah",
        plant_name="Kirah Plant",
        alarm_id="alarm-1",
        alarm_code="pump_fault",
        event_id="event-1",
        timestamp="2026-04-16T18:00:00Z",
        priority="critical",
        category="state",
        title="Pump Fault",
        description="Pump 1 entered fault state",
        value_actual="{'previous_state': 1, 'state': 3}",
        threshold="from_states=[1, 2] -> to_state=3",
        recipients=["ops@example.com", "boss@example.com"],
        level="lvl2",
        tag_id="P101_ST_SCADA",
        reason="transicion_estado",
    )


def test_render_alarm_template_contains_key_fields():
    service = EmailService(settings_obj=_build_settings(), mail_client=_DummyMailClient())
    payload = _build_payload()

    html = service.render_template(
        "alarm_notification.html",
        {"payload": payload, "subject": payload.subject},
    )

    assert "Kirah Plant" in html
    assert "Pump Fault" in html
    assert "SCADA Alarm Notification" in html
    assert "Current Value" in html
    assert "Threshold" in html
    assert "ops@example.com" not in html
    assert "from_states=[1, 2] -&gt; to_state=3" in html


def test_send_alarm_notification_builds_html_message():
    mail_client = _DummyMailClient()
    service = EmailService(settings_obj=_build_settings(), mail_client=mail_client)
    payload = _build_payload()

    asyncio.run(service.send_alarm_notification(payload))

    assert len(mail_client.messages) == 1
    message = mail_client.messages[0]
    assert message.subject == "[LVL2] Kirah Plant - Pump Fault"
    assert [recipient.email for recipient in message.recipients] == [
        "ops@example.com",
        "boss@example.com",
    ]
    assert "Pump 1 entered fault state" in message.body


def test_notification_orchestrator_swallows_smtp_errors():
    failing_service = EmailService(
        settings_obj=_build_settings(),
        mail_client=_DummyMailClient(should_fail=True),
    )
    orchestrator = NotificationOrchestrator(
        email_service=failing_service,
        max_workers=1,
    )

    orchestrator.dispatch_now(
        [
            orchestrator.build_email_job(_build_payload()),
        ]
    )

    assert True


def test_alarm_payload_normalizes_csv_recipients():
    payload = AlarmNotificationPayload(
        lagoon_id="kirah",
        plant_name="Kirah Plant",
        alarm_id="alarm-1",
        alarm_code="pump_fault",
        event_id="event-1",
        timestamp="2026-04-16T18:00:00Z",
        priority="warning",
        category="state",
        title="Pump Fault",
        description="Pump 1 entered fault state",
        recipients="ops@example.com;boss@example.com,ops@example.com",
    )

    assert payload.recipients == ["ops@example.com", "boss@example.com"]
