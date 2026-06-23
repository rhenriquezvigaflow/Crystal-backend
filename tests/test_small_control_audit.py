from __future__ import annotations

from app.services.small_control_audit import (
    begin_control_audit,
    complete_control_audit,
    fail_control_audit,
)


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.commits = 0

    def add(self, value) -> None:
        self.added.append(value)

    def commit(self) -> None:
        self.commits += 1

    def refresh(self, _value) -> None:
        pass


def test_control_audit_records_user_change_and_completion() -> None:
    db = FakeSession()
    audit = begin_control_audit(
        db,
        lagoon_id="small_sim",
        module_id="recirculation_pump",
        control_type="value_write",
        action="change_value",
        command_id="set_tags_03_int",
        new_value=30,
        change_summary="Value change requested for set_tags_03_int",
        user_id="35",
        user_email="operator@example.com",
    )

    complete_control_audit(
        db,
        audit,
        tag_id="TAGS_03_INT",
        node_id="ns=4;i=15",
        previous_value=0,
        new_value=30,
        change_summary="TAGS_03_INT changed from 0 to 30",
    )

    assert audit.user_id == "35"
    assert audit.user_email == "operator@example.com"
    assert audit.previous_value == 0
    assert audit.new_value == 30
    assert audit.status == "success"
    assert audit.completed_at is not None
    assert db.commits == 2


def test_control_audit_records_failed_command() -> None:
    db = FakeSession()
    audit = begin_control_audit(
        db,
        lagoon_id="small_sim",
        module_id="recirculation_pump",
        control_type="pump_action",
        action="start",
        new_value={"action": "start"},
        change_summary="Pump start command requested",
        user_id="35",
        user_email="operator@example.com",
    )

    fail_control_audit(db, audit, RuntimeError("PLC unavailable"))

    assert audit.status == "failed"
    assert audit.error_detail == "PLC unavailable"
    assert audit.completed_at is not None
