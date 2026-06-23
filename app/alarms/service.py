from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from fnmatch import fnmatch
from typing import Any, Mapping

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.alarms.models import (
    ALARM_TYPE_COMM_LOSS,
    ALARM_TYPE_STATE,
    ALARM_TYPE_THRESHOLD,
    AlarmDefinition,
    AlarmEvent,
)
from app.alarms.repository import AlarmRepository, deduplicate_rules
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.notifications import AlarmNotificationPayload, NotificationJob

logger = get_logger("alarms.service")
_comm_loss_last_seen: dict[object, datetime] = {}
DEFAULT_TAG_COMM_LOSS_TIMEOUT_SEC = settings.ALARM_TAG_COMM_LOSS_TIMEOUT_SEC
DEFAULT_LAGOON_COMM_LOSS_TIMEOUT_SEC = settings.ALARM_LAGOON_COMM_LOSS_TIMEOUT_SEC


@dataclass(slots=True)
class AlarmTransition:
    """Transicion de estado generada por el motor de alarmas."""

    transition: str
    event_id: str
    alarm_definition_id: str
    alarm_code: str
    lagoon_id: str
    tag_id: str | None
    alarm_type: str
    severity: str
    happened_at: datetime
    value: Any
    reason: str
    duration_sec: int | None = None


@dataclass(slots=True)
class EvaluationDecision:
    """
    Resultado de evaluar una definicion.

    `should_alarm`:
    - True  -> condicion de alarma activa
    - False -> estado normal
    - None  -> no se puede evaluar con el payload actual
    """

    should_alarm: bool | None
    value: Any
    reason: str


def log_persisted_alarm_transitions(
    transitions: list[AlarmTransition],
) -> None:
    for transition in transitions:
        if transition.transition == "OPEN":
            logger.warning(
                "[ALARM OPEN] lagoon=%s code=%s tag=%s type=%s severity=%s event=%s reason=%s",
                transition.lagoon_id,
                transition.alarm_code,
                transition.tag_id,
                transition.alarm_type,
                transition.severity,
                transition.event_id,
                transition.reason,
            )
            continue

        logger.info(
            "[ALARM CLOSE] lagoon=%s code=%s tag=%s type=%s severity=%s event=%s duration_sec=%s reason=%s",
            transition.lagoon_id,
            transition.alarm_code,
            transition.tag_id,
            transition.alarm_type,
            transition.severity,
            transition.event_id,
            transition.duration_sec,
            transition.reason,
        )


def _get_comm_loss_last_seen(definition: AlarmDefinition) -> datetime | None:
    cached = _comm_loss_last_seen.get(definition.id)
    if cached is not None:
        return _ensure_utc(cached)

    if definition.last_seen_ts is None:
        return None

    normalized = _ensure_utc(definition.last_seen_ts)
    _comm_loss_last_seen[definition.id] = normalized
    return normalized


def _set_comm_loss_last_seen(
    definition: AlarmDefinition,
    ts: datetime,
) -> None:
    _comm_loss_last_seen[definition.id] = _ensure_utc(ts)


def evaluate_alarms(
    payload: Mapping[str, Any],
    db: Session,
) -> tuple[list[AlarmTransition], list[NotificationJob]]:
    """
    Evalua todas las definiciones de alarma relevantes para un payload SCADA.

    Retorna:
    - `transitions`: eventos OPEN/CLOSE generados en este ciclo.
    - `notification_jobs`: notificaciones enrutadas para despachar post-commit.
    """
    lagoon_id = str(payload["lagoon_id"])
    source_ts = _ensure_utc(payload["timestamp"])
    tags = dict(payload.get("tags") or {})

    definitions = AlarmRepository.get_definitions(
        db=db,
        lagoon_id=lagoon_id,
        tags=tags,
    )
    definition_ids = [definition.id for definition in definitions]
    active_alarms_by_definition = AlarmRepository.get_active_alarms_map(
        db=db,
        alarm_definition_ids=definition_ids,
    )

    transition_state_tags = {
        definition.tag_id
        for definition in definitions
        if (
            definition.alarm_type == ALARM_TYPE_STATE
            and isinstance(definition.tag_id, str)
            and definition.tag_id in tags
            and isinstance(definition.condition, dict)
            and "to_state" in definition.condition
            and "from_states" in definition.condition
        )
    }
    latest_transitions_by_tag = AlarmRepository.get_latest_scada_transitions_map(
        db=db,
        lagoon_id=lagoon_id,
        tag_ids=transition_state_tags,
        at_or_before=source_ts,
    )

    transitions: list[AlarmTransition] = []
    notifications: list[NotificationJob] = []

    for definition in definitions:
        active_event = active_alarms_by_definition.get(definition.id)

        decision = _evaluate_definition(
            definition=definition,
            tags=tags,
            source_ts=source_ts,
            db=db,
            active_event=active_event,
            latest_transitions_by_tag=latest_transitions_by_tag,
        )

        if decision.should_alarm is None:
            continue

        transition: AlarmTransition | None = None

        if decision.should_alarm and active_event is None:
            transition = open_alarm(
                db=db,
                definition=definition,
                source_ts=source_ts,
                value=decision.value,
                reason=decision.reason,
            )
        elif (not decision.should_alarm) and active_event is not None:
            transition = close_alarm(
                db=db,
                definition=definition,
                source_ts=source_ts,
                value=decision.value,
                reason=decision.reason,
            )

        if transition is None:
            continue

        transitions.append(transition)
        if transition.transition == "OPEN":
            notifications.extend(
                _route_notifications(
                    db=db,
                    definition=definition,
                    transition=transition,
                )
            )

    return transitions, notifications


def evaluate_lagoon_signal_alarms(
    db: Session,
    now_utc: datetime | None = None,
) -> tuple[list[AlarmTransition], list[NotificationJob]]:
    """
    Evalua alarmas comm_loss a nivel laguna usando reloj del servidor.

    Se usa cuando el collector no envia telemetria continua y solo publica eventos
    por cambio de estado.
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    now_utc = _ensure_utc(now_utc)

    definitions = AlarmRepository.get_lagoon_comm_loss_definitions(db=db)
    definition_ids = [definition.id for definition in definitions]
    active_alarms_by_definition = AlarmRepository.get_active_alarms_map(
        db=db,
        alarm_definition_ids=definition_ids,
    )

    transitions: list[AlarmTransition] = []
    notifications: list[NotificationJob] = []

    for definition in definitions:
        active_event = active_alarms_by_definition.get(definition.id)

        decision = _evaluate_lagoon_comm_loss_by_clock(
            definition=definition,
            now_utc=now_utc,
            db=db,
        )

        if decision.should_alarm is None:
            continue

        transition: AlarmTransition | None = None
        if decision.should_alarm and active_event is None:
            transition = open_alarm(
                db=db,
                definition=definition,
                source_ts=now_utc,
                value=None,
                reason=decision.reason,
            )
        elif (not decision.should_alarm) and active_event is not None:
            transition = close_alarm(
                db=db,
                definition=definition,
                source_ts=now_utc,
                value=None,
                reason=decision.reason,
            )

        if transition is None:
            continue

        transitions.append(transition)
        if transition.transition == "OPEN":
            notifications.extend(
                _route_notifications(
                    db=db,
                    definition=definition,
                    transition=transition,
                )
            )

    return transitions, notifications


def open_alarm(
    db: Session,
    definition: AlarmDefinition,
    source_ts: datetime,
    value: Any,
    reason: str,
) -> AlarmTransition | None:
    """
    Abre un nuevo evento de alarma si no existe uno activo.

    Idempotencia:
    - lock de fila sobre la definicion
    - re-chequeo de evento activo
    """
    AlarmRepository.lock_definition(db=db, definition_id=definition.id)

    active_event = AlarmRepository.get_active_alarm(
        db=db,
        alarm_definition_id=definition.id,
    )
    if active_event is not None:
        return None

    event = AlarmRepository.create_event(
        db=db,
        definition=definition,
        opened_at=source_ts,
        source_ts=source_ts,
        open_value=_safe_str(value),
        open_reason=reason,
    )

    return AlarmTransition(
        transition="OPEN",
        event_id=str(event.id),
        alarm_definition_id=str(definition.id),
        alarm_code=definition.code,
        lagoon_id=definition.lagoon_id,
        tag_id=definition.tag_id,
        alarm_type=definition.alarm_type,
        severity=definition.severity,
        happened_at=source_ts,
        value=value,
        reason=reason,
    )


def close_alarm(
    db: Session,
    definition: AlarmDefinition,
    source_ts: datetime,
    value: Any,
    reason: str,
) -> AlarmTransition | None:
    """Cierra el evento de alarma activo de una definicion."""
    AlarmRepository.lock_definition(db=db, definition_id=definition.id)

    event = AlarmRepository.get_active_alarm(
        db=db,
        alarm_definition_id=definition.id,
    )
    if event is None:
        return None

    event = AlarmRepository.close_event(
        db=db,
        event=event,
        closed_at=source_ts,
        close_value=_safe_str(value),
        close_reason=reason,
    )

    return AlarmTransition(
        transition="CLOSE",
        event_id=str(event.id),
        alarm_definition_id=str(definition.id),
        alarm_code=definition.code,
        lagoon_id=definition.lagoon_id,
        tag_id=definition.tag_id,
        alarm_type=definition.alarm_type,
        severity=definition.severity,
        happened_at=source_ts,
        value=value,
        reason=reason,
        duration_sec=event.duration_sec,
    )


def _route_notifications(
    db: Session,
    definition: AlarmDefinition,
    transition: AlarmTransition,
) -> list[NotificationJob]:
    rules = AlarmRepository.get_notification_rules(
        db=db,
        definition=definition,
        transition=transition.transition,
    )
    lagoon_name: str | None = None

    if not rules:
        logger.debug(
            "[NOTIFY SKIP] reason=no_routing_rules definition=%s lagoon=%s tag=%s type=%s severity=%s event=%s",
            definition.id,
            transition.lagoon_id,
            transition.tag_id,
            transition.alarm_type,
            transition.severity,
            transition.event_id,
        )
        return []

    matching_rules = [
        rule
        for rule in rules
        if _tag_matches(rule.tag_pattern, definition.tag_id)
    ]
    matching_rules = deduplicate_rules(matching_rules)

    jobs: list[NotificationJob] = []
    for rule in matching_rules:
        alarm_payload: AlarmNotificationPayload | None = None
        if rule.channel == "email":
            if lagoon_name is None:
                lagoon_name = AlarmRepository.get_lagoon_name(
                    db=db,
                    lagoon_id=definition.lagoon_id,
                )
            try:
                alarm_payload = _build_alarm_notification_payload(
                    definition=definition,
                    transition=transition,
                    lagoon_name=lagoon_name,
                    target=rule.target,
                )
            except ValidationError:
                logger.warning(
                    "[NOTIFY RULE SKIP] channel=%s target=%s lagoon=%s definition=%s reason=invalid_email_target",
                    rule.channel,
                    rule.target,
                    definition.lagoon_id,
                    definition.id,
                )
                continue

        jobs.append(
            NotificationJob(
                channel=rule.channel,
                target=rule.target,
                transition=transition.transition,
                alarm_type=transition.alarm_type,
                severity=transition.severity,
                lagoon_id=transition.lagoon_id,
                tag_id=transition.tag_id,
                event_id=transition.event_id,
                happened_at=transition.happened_at,
                message=_render_notification_message(
                    definition=definition,
                    transition=transition,
                ),
                alarm_payload=alarm_payload,
            )
        )

    if not jobs:
        logger.debug(
            "[NOTIFY SKIP] reason=no_matching_targets definition=%s lagoon=%s tag=%s type=%s severity=%s event=%s candidate_rules=%s matched_rules=%s",
            definition.id,
            transition.lagoon_id,
            transition.tag_id,
            transition.alarm_type,
            transition.severity,
            transition.event_id,
            len(rules),
            len(matching_rules),
        )

    return jobs


def _build_alarm_notification_payload(
    definition: AlarmDefinition,
    transition: AlarmTransition,
    lagoon_name: str | None,
    target: str,
) -> AlarmNotificationPayload:
    threshold = _format_threshold(definition.condition)
    return AlarmNotificationPayload(
        lagoon_id=transition.lagoon_id,
        plant_name=lagoon_name,
        alarm_id=str(definition.id),
        alarm_code=definition.code,
        event_id=transition.event_id,
        timestamp=transition.happened_at,
        priority=transition.severity,
        category=transition.alarm_type,
        title=_build_email_title(definition=definition, transition=transition),
        description=_build_email_description(
            definition=definition,
            transition=transition,
            threshold=threshold,
        ),
        value_actual=_safe_str(transition.value),
        threshold=threshold,
        recipients=target,
        level=_notification_level(transition.severity),
        tag_id=transition.tag_id,
        transition=transition.transition,
        reason=transition.reason,
    )


def _evaluate_definition(
    definition: AlarmDefinition,
    tags: Mapping[str, Any],
    source_ts: datetime,
    db: Session,
    active_event: AlarmEvent | None,
    latest_transitions_by_tag: Mapping[str, Any],
) -> EvaluationDecision:
    if definition.alarm_type == ALARM_TYPE_THRESHOLD:
        return _evaluate_threshold(
            definition=definition,
            tags=tags,
            active_event=active_event,
        )

    if definition.alarm_type == ALARM_TYPE_STATE:
        return _evaluate_state(
            definition=definition,
            tags=tags,
            latest_transitions_by_tag=latest_transitions_by_tag,
        )

    if definition.alarm_type == ALARM_TYPE_COMM_LOSS:
        return _evaluate_comm_loss(
            definition=definition,
            tags=tags,
            source_ts=source_ts,
            db=db,
        )

    return EvaluationDecision(
        should_alarm=None,
        value=None,
        reason="tipo_alarma_no_soportado",
    )


def _evaluate_threshold(
    definition: AlarmDefinition,
    tags: Mapping[str, Any],
    active_event: AlarmEvent | None,
) -> EvaluationDecision:
    tag_id = definition.tag_id
    if not tag_id or tag_id not in tags:
        return EvaluationDecision(
            should_alarm=None,
            value=None,
            reason="tag_ausente",
        )

    numeric_value = _to_float(tags[tag_id])
    if numeric_value is None:
        return EvaluationDecision(
            should_alarm=None,
            value=tags[tag_id],
            reason="valor_no_numerico",
        )

    condition = definition.condition or {}
    deadband = _to_float(condition.get("deadband"))
    if deadband is None:
        deadband = float(definition.deadband or 0.0)

    op = str(condition.get("op", "")).strip().lower()
    op_target = _to_float(condition.get("value"))

    if op and op_target is not None:
        violated = _compare_numeric(
            left=numeric_value,
            op=op,
            right=op_target,
            deadband=deadband if active_event else 0.0,
            active=active_event is not None,
        )
        return EvaluationDecision(
            should_alarm=violated,
            value=numeric_value,
            reason=f"umbral_operador:{op}:{op_target}",
        )

    low = _to_float(condition.get("low"))
    high = _to_float(condition.get("high"))
    if low is None and high is None:
        return EvaluationDecision(
            should_alarm=None,
            value=numeric_value,
            reason="umbral_sin_limites",
        )

    low_limit = low
    high_limit = high

    if active_event is not None:
        if low_limit is not None:
            low_limit = low_limit + deadband
        if high_limit is not None:
            high_limit = high_limit - deadband

    below = low_limit is not None and numeric_value < low_limit
    above = high_limit is not None and numeric_value > high_limit
    violated = below or above

    return EvaluationDecision(
        should_alarm=violated,
        value=numeric_value,
        reason=f"umbral_rango:bajo={low_limit}:alto={high_limit}",
    )


def _evaluate_state(
    definition: AlarmDefinition,
    tags: Mapping[str, Any],
    latest_transitions_by_tag: Mapping[str, Any],
) -> EvaluationDecision:
    tag_id = definition.tag_id
    if not tag_id or tag_id not in tags:
        return EvaluationDecision(
            should_alarm=None,
            value=None,
            reason="tag_ausente",
        )

    current_value = tags[tag_id]
    condition = definition.condition or {}

    if "to_state" in condition and "from_states" in condition:
        to_state = _to_int(condition.get("to_state"))
        from_states = _to_int_list(condition.get("from_states"))

        if to_state is None or not from_states:
            return EvaluationDecision(
                should_alarm=None,
                value=current_value,
                reason="condicion_transicion_invalida",
            )

        latest_transition = latest_transitions_by_tag.get(tag_id)

        if (
            latest_transition is None
            or latest_transition.previous_state is None
            or latest_transition.state is None
        ):
            return EvaluationDecision(
                should_alarm=False,
                value=current_value,
                reason="sin_transicion_reciente",
            )

        previous_state = int(latest_transition.previous_state)
        current_state = int(latest_transition.state)
        violated = (
            previous_state in set(from_states)
            and current_state == to_state
        )

        return EvaluationDecision(
            should_alarm=violated,
            value={
                "previous_state": previous_state,
                "state": current_state,
            },
            reason=(
                f"transicion_estado:{previous_state}->{current_state}:"
                f"objetivo={from_states}->{to_state}"
            ),
        )

    if "equals" in condition:
        expected = condition["equals"]
        violated = current_value == expected
        return EvaluationDecision(
            should_alarm=violated,
            value=current_value,
            reason=f"estado_igual_a:{expected}",
        )

    if "states" in condition:
        values = condition.get("states")
        if not isinstance(values, list):
            return EvaluationDecision(
                should_alarm=None,
                value=current_value,
                reason="lista_estados_invalida",
            )
        violated = current_value in values
        return EvaluationDecision(
            should_alarm=violated,
            value=current_value,
            reason=f"estado_en:{values}",
        )

    if "not_in" in condition:
        values = condition.get("not_in")
        if not isinstance(values, list):
            return EvaluationDecision(
                should_alarm=None,
                value=current_value,
                reason="lista_not_in_invalida",
            )
        violated = current_value not in values
        return EvaluationDecision(
            should_alarm=violated,
            value=current_value,
            reason=f"estado_no_en:{values}",
        )

    return EvaluationDecision(
        should_alarm=None,
        value=current_value,
        reason="condicion_de_estado_no_configurada",
    )


def _evaluate_comm_loss(
    definition: AlarmDefinition,
    tags: Mapping[str, Any],
    source_ts: datetime,
    db: Session,
) -> EvaluationDecision:
    tag_id = definition.tag_id
    condition = definition.condition or {}

    timeout_sec = _to_float(condition.get("timeout_sec"))
    timeout_sec = (
        timeout_sec
        if timeout_sec is not None
        else DEFAULT_TAG_COMM_LOSS_TIMEOUT_SEC
    )

    if not tag_id:
        # A nivel laguna, comm-loss no puede disparar desde esta ruta,
        # porque este evaluador corre solo cuando entra ingest.
        _set_comm_loss_last_seen(definition, source_ts)
        return EvaluationDecision(
            should_alarm=False,
            value=None,
            reason="comm_loss_laguna_observada",
        )

    tag_in_payload = tag_id in tags and tags.get(tag_id) is not None
    if tag_in_payload:
        _set_comm_loss_last_seen(definition, source_ts)
        return EvaluationDecision(
            should_alarm=False,
            value=tags[tag_id],
            reason="comunicacion_restaurada",
        )

    last_seen_ts = _get_comm_loss_last_seen(definition)
    if last_seen_ts is None:
        _set_comm_loss_last_seen(definition, source_ts)
        return EvaluationDecision(
            should_alarm=False,
            value=None,
            reason="baseline_comunicacion_inicializada",
        )

    age_sec = (source_ts - last_seen_ts).total_seconds()
    violated = age_sec > timeout_sec

    return EvaluationDecision(
        should_alarm=violated,
        value=None,
        reason=f"comm_loss_edad_seg:{age_sec:.2f}:timeout_seg:{timeout_sec:.2f}",
    )


def _evaluate_lagoon_comm_loss_by_clock(
    definition: AlarmDefinition,
    now_utc: datetime,
    db: Session,
) -> EvaluationDecision:
    condition = definition.condition or {}

    timeout_sec = _to_float(condition.get("timeout_sec"))
    timeout_sec = (
        timeout_sec
        if timeout_sec is not None
        else DEFAULT_LAGOON_COMM_LOSS_TIMEOUT_SEC
    )

    last_seen_ts = _get_comm_loss_last_seen(definition)
    if last_seen_ts is None:
        _set_comm_loss_last_seen(definition, now_utc)
        return EvaluationDecision(
            should_alarm=False,
            value=None,
            reason="baseline_laguna_inicializada",
        )

    age_sec = (now_utc - last_seen_ts).total_seconds()
    age_sec = max(age_sec, 0.0)
    violated = age_sec > timeout_sec

    if violated:
        return EvaluationDecision(
            should_alarm=True,
            value=None,
            reason=f"laguna_sin_senal_edad_seg:{age_sec:.2f}:timeout_seg:{timeout_sec:.2f}",
        )

    return EvaluationDecision(
        should_alarm=False,
        value=None,
        reason=f"laguna_con_senal_edad_seg:{age_sec:.2f}:timeout_seg:{timeout_sec:.2f}",
    )


def _compare_numeric(
    left: float,
    op: str,
    right: float,
    deadband: float,
    active: bool,
) -> bool:
    normalized = op.strip().lower()
    if normalized == ">":
        threshold = right - deadband if active else right
        return left > threshold
    if normalized == ">=":
        threshold = right - deadband if active else right
        return left >= threshold
    if normalized == "<":
        threshold = right + deadband if active else right
        return left < threshold
    if normalized == "<=":
        threshold = right + deadband if active else right
        return left <= threshold
    if normalized == "==":
        return left == right
    if normalized in {"!=", "<>"}:
        return left != right
    return False


def _tag_matches(
    pattern: str | None,
    tag_id: str | None,
) -> bool:
    if not pattern:
        return True
    if not tag_id:
        return False

    normalized_pattern = pattern.strip()
    if not normalized_pattern:
        return True

    # Backward compatibility:
    # historic DB rules used SQL-LIKE '%' wildcards.
    normalized_pattern = normalized_pattern.replace("%", "*")

    return fnmatch(tag_id, normalized_pattern)


def _render_notification_message(
    definition: AlarmDefinition,
    transition: AlarmTransition,
) -> str:
    return (
        f"alarma={definition.code} "
        f"nombre={definition.name} "
        f"transicion={transition.transition} "
        f"lagoon_id={transition.lagoon_id} "
        f"tag_id={transition.tag_id} "
        f"valor={transition.value} "
        f"motivo={transition.reason}"
    )


def _build_email_title(
    definition: AlarmDefinition,
    transition: AlarmTransition,
) -> str:
    target = transition.tag_id or transition.lagoon_id

    if transition.alarm_type == ALARM_TYPE_THRESHOLD:
        return f"Threshold alarm for {target}"

    if transition.alarm_type == ALARM_TYPE_STATE:
        return f"State alarm for {target}"

    if transition.alarm_type == ALARM_TYPE_COMM_LOSS:
        if transition.tag_id:
            return f"Communication loss alarm for {transition.tag_id}"
        return f"Communication loss alarm for lagoon {transition.lagoon_id}"

    return f"Alarm for {target}"


def _build_email_description(
    definition: AlarmDefinition,
    transition: AlarmTransition,
    threshold: str | None,
) -> str:
    target = transition.tag_id or transition.lagoon_id
    current_value = _safe_str(transition.value) or "n/a"

    if transition.alarm_type == ALARM_TYPE_THRESHOLD:
        if threshold:
            return (
                f"A threshold condition was triggered for {target}. "
                f"Current value: {current_value}. Rule: {threshold}."
            )
        return (
            f"A threshold condition was triggered for {target}. "
            f"Current value: {current_value}."
        )

    if transition.alarm_type == ALARM_TYPE_STATE:
        return (
            f"A state-based alarm was triggered for {target}. "
            f"Current value: {current_value}."
        )

    if transition.alarm_type == ALARM_TYPE_COMM_LOSS:
        if transition.tag_id:
            return f"A communication loss alarm was triggered for {transition.tag_id}."
        return (
            f"A communication loss alarm was triggered for lagoon "
            f"{transition.lagoon_id}."
        )

    return f"An alarm was triggered for {target}."


def _notification_level(severity: str) -> str:
    normalized = severity.strip().lower()
    if normalized in {"critical", "high"}:
        return "lvl2"
    return "lvl1"


def _format_threshold(condition: Any) -> str | None:
    if not isinstance(condition, dict):
        return None

    op = str(condition.get("op", "")).strip()
    op_value = condition.get("value")
    if op and op_value is not None:
        return f"{op} {op_value}"

    low = condition.get("low")
    high = condition.get("high")
    if low is not None or high is not None:
        parts: list[str] = []
        if low is not None:
            parts.append(f"min={low}")
        if high is not None:
            parts.append(f"max={high}")
        return " | ".join(parts)

    timeout_sec = condition.get("timeout_sec")
    if timeout_sec is not None:
        return f"timeout_sec={timeout_sec}"

    to_state = condition.get("to_state")
    from_states = condition.get("from_states")
    if to_state is not None and from_states is not None:
        return f"from_states={from_states} -> to_state={to_state}"

    equals = condition.get("equals")
    if equals is not None:
        return f"equals {equals}"

    states = condition.get("states")
    if states is not None:
        return f"states={states}"

    return None


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_int_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []

    result: list[int] = []
    for item in value:
        converted = _to_int(item)
        if converted is None:
            continue
        result.append(converted)

    return result


def _safe_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _ensure_utc(value: Any) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("payload.timestamp debe ser datetime")
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
