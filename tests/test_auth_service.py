from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.auth.jwt import ACCESS_TOKEN_EXPIRE_MINUTES
from app.alarms.service import _evaluate_lagoon_comm_loss_by_clock
from app.auth.services.auth_service import build_login_response


def _build_user() -> SimpleNamespace:
    return SimpleNamespace(
        id=123,
        email="operator@example.com",
        roles=[SimpleNamespace(name="ADMIN")],
        role=None,
    )


def test_build_login_response_uses_18_hour_expiry():
    response = build_login_response(_build_user())

    assert ACCESS_TOKEN_EXPIRE_MINUTES == 18 * 60
    assert response["expires_in"] == 18 * 60 * 60
    assert response["token_type"] == "bearer"
    assert response["user"]["roles"] == ["ADMIN"]


def test_lagoon_comm_loss_default_timeout_is_6_hours():
    now_utc = datetime.now(timezone.utc)
    before_timeout_definition = SimpleNamespace(
        id=uuid4(),
        condition={},
        last_seen_ts=now_utc - timedelta(hours=5, minutes=59),
    )

    before_timeout = _evaluate_lagoon_comm_loss_by_clock(
        definition=before_timeout_definition,
        now_utc=now_utc,
        db=None,
    )

    assert before_timeout.should_alarm is False
    assert "timeout_seg:21600.00" in before_timeout.reason

    after_timeout_definition = SimpleNamespace(
        id=uuid4(),
        condition={},
        last_seen_ts=now_utc - timedelta(hours=6, minutes=1),
    )
    after_timeout = _evaluate_lagoon_comm_loss_by_clock(
        definition=after_timeout_definition,
        now_utc=now_utc,
        db=None,
    )

    assert after_timeout.should_alarm is True
    assert "timeout_seg:21600.00" in after_timeout.reason
