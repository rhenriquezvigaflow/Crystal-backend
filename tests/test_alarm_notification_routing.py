from __future__ import annotations

from datetime import datetime, timezone

from app.alarms.models import AlarmDefinition, AlarmNotificationRule
from app.alarms.service import AlarmTransition, _route_notifications


def test_route_notifications_keeps_matching_rule_when_targets_repeat(monkeypatch):
    definition = AlarmDefinition(
        id="definition-1",
        lagoon_id="ava_lagoons",
        tag_id="PT145_R_SCADA",
        code="threshold_pt145_r_scada_min",
        name="PT145 min threshold",
        alarm_type="threshold",
        severity="critical",
        condition={"op": "<", "value": 1.07},
    )
    transition = AlarmTransition(
        transition="OPEN",
        event_id="event-1",
        alarm_definition_id="definition-1",
        alarm_code="threshold_pt145_r_scada_min",
        lagoon_id="ava_lagoons",
        tag_id="PT145_R_SCADA",
        alarm_type="threshold",
        severity="critical",
        happened_at=datetime(2026, 4, 17, 4, 54, 43, tzinfo=timezone.utc),
        value=0.91,
        reason="umbral_operador:<:1.07",
    )

    fit_rule = AlarmNotificationRule(
        id="rule-fit",
        enabled=True,
        scope="global",
        lagoon_id=None,
        alarm_definition_id=None,
        alarm_type="threshold",
        severity="critical",
        tag_pattern="FIT*",
        channel="email",
        target="rhenriquez@vigaflow.com",
    )
    pt_rule = AlarmNotificationRule(
        id="rule-pt",
        enabled=True,
        scope="global",
        lagoon_id=None,
        alarm_definition_id=None,
        alarm_type="threshold",
        severity="critical",
        tag_pattern="PT*",
        channel="email",
        target="rhenriquez@vigaflow.com",
    )

    monkeypatch.setattr(
        "app.alarms.service.AlarmRepository.get_notification_rules",
        lambda **_kwargs: [fit_rule, pt_rule],
    )
    monkeypatch.setattr(
        "app.alarms.service.AlarmRepository.get_lagoon_name",
        lambda **_kwargs: "Ava Lagoons",
    )

    jobs = _route_notifications(
        db=None,
        definition=definition,
        transition=transition,
    )

    assert len(jobs) == 1
    assert jobs[0].channel == "email"
    assert jobs[0].target == "rhenriquez@vigaflow.com"
    assert jobs[0].tag_id == "PT145_R_SCADA"
