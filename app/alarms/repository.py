from __future__ import annotations

from datetime import datetime
from typing import Iterable, Mapping

from sqlalchemy import and_, or_, text
from sqlalchemy.orm import Session

from app.alarms.models import (
    ALARM_TYPE_COMM_LOSS,
    ALARM_TYPE_THRESHOLD,
    AlarmDefinition,
    AlarmEvent,
    AlarmNotificationRule,
)
from app.models.scada_event import ScadaEvent


class AlarmRepository:
    """Capa de acceso a datos para definiciones, eventos y reglas de notificacion."""

    @staticmethod
    def get_definitions(
        db: Session,
        lagoon_id: str,
        tags: Mapping[str, object],
    ) -> list[AlarmDefinition]:
        """
        Retorna las definiciones habilitadas que pueden evaluarse con el payload entrante.

        - `threshold/state`: se evaluan cuando el tag de la definicion viene en el payload.
        - `comm_loss`: siempre se evalua para la laguna.
        """
        tag_ids = set(tags.keys())

        query = (
            db.query(AlarmDefinition)
            .filter(
                AlarmDefinition.enabled.is_(True),
                AlarmDefinition.lagoon_id == lagoon_id,
            )
        )

        if tag_ids:
            query = query.filter(
                or_(
                    AlarmDefinition.alarm_type == ALARM_TYPE_COMM_LOSS,
                    AlarmDefinition.tag_id.in_(tag_ids),
                )
            )
        else:
            query = query.filter(
                AlarmDefinition.alarm_type == ALARM_TYPE_COMM_LOSS,
            )

        return (
            query.order_by(
                AlarmDefinition.alarm_type.asc(),
                AlarmDefinition.tag_id.asc().nulls_last(),
                AlarmDefinition.id.asc(),
            )
            .all()
        )

    @staticmethod
    def get_lagoon_comm_loss_definitions(
        db: Session,
    ) -> list[AlarmDefinition]:
        """
        Retorna definiciones comm_loss a nivel laguna (tag_id NULL).
        """
        return (
            db.query(AlarmDefinition)
            .filter(
                AlarmDefinition.enabled.is_(True),
                AlarmDefinition.alarm_type == ALARM_TYPE_COMM_LOSS,
                AlarmDefinition.tag_id.is_(None),
            )
            .order_by(
                AlarmDefinition.lagoon_id.asc(),
                AlarmDefinition.id.asc(),
            )
            .all()
        )

    @staticmethod
    def get_pt_fit_threshold_definitions(
        db: Session,
        lagoon_id: str,
    ) -> list[AlarmDefinition]:
        """
        Retorna alarmas threshold para tags PT/FIT de una laguna.
        """
        return (
            db.query(AlarmDefinition)
            .filter(
                AlarmDefinition.lagoon_id == lagoon_id,
                AlarmDefinition.alarm_type == ALARM_TYPE_THRESHOLD,
                or_(
                    AlarmDefinition.tag_id.ilike("PT%"),
                    AlarmDefinition.tag_id.ilike("FIT%"),
                ),
            )
            .order_by(
                AlarmDefinition.tag_id.asc(),
                AlarmDefinition.code.asc(),
            )
            .all()
        )

    @staticmethod
    def get_definition_by_code(
        db: Session,
        lagoon_id: str,
        code: str,
    ) -> AlarmDefinition | None:
        """
        Busca una definicion por lagoon_id + code.
        """
        return (
            db.query(AlarmDefinition)
            .filter(
                AlarmDefinition.lagoon_id == lagoon_id,
                AlarmDefinition.code == code,
            )
            .first()
        )

    @staticmethod
    def get_pt_fit_candidate_tags(
        db: Session,
        lagoon_id: str,
    ) -> list[dict]:
        """
        Retorna tags PT/FIT detectados en historico con su ultimo valor observado.
        """
        rows = db.execute(
            text(
                """
                SELECT DISTINCT ON (m.tag_id)
                    m.tag_id,
                    m.bucket AS last_ts,
                    m.state,
                    m.value_num,
                    m.value_bool
                FROM scada_minute m
                WHERE m.lagoon_id = :lagoon_id
                  AND (
                      upper(m.tag_id) LIKE 'PT%%'
                      OR upper(m.tag_id) LIKE 'FIT%%'
                  )
                ORDER BY m.tag_id, m.bucket DESC
                """
            ),
            {"lagoon_id": lagoon_id},
        ).mappings().all()

        candidates: list[dict] = []
        for row in rows:
            value = row["state"]
            if value is None:
                value = row["value_num"]
            if value is None:
                value = row["value_bool"]

            candidates.append(
                {
                    "tag_id": row["tag_id"],
                    "last_ts": row["last_ts"],
                    "last_value": value,
                }
            )

        return candidates

    @staticmethod
    def get_latest_scada_transition(
        db: Session,
        lagoon_id: str,
        tag_id: str,
        at_or_before: datetime | None = None,
    ) -> ScadaEvent | None:
        """
        Retorna el ultimo cambio de estado SCADA para lagoon/tag.
        """
        query = (
            db.query(ScadaEvent)
            .filter(
                ScadaEvent.lagoon_id == lagoon_id,
                ScadaEvent.tag_id == tag_id,
            )
        )

        if at_or_before is not None:
            query = query.filter(ScadaEvent.start_ts <= at_or_before)

        return (
            query.order_by(
                ScadaEvent.start_ts.desc(),
                ScadaEvent.created_at.desc(),
            )
            .first()
        )

    @staticmethod
    def get_latest_scada_transitions_map(
        db: Session,
        lagoon_id: str,
        tag_ids: Iterable[str],
        at_or_before: datetime | None = None,
    ) -> dict[str, ScadaEvent]:
        """
        Retorna la ultima transicion SCADA por tag en una sola consulta.
        """
        normalized_tag_ids = {
            str(tag_id).strip()
            for tag_id in tag_ids
            if isinstance(tag_id, str) and str(tag_id).strip()
        }
        if not normalized_tag_ids:
            return {}

        query = (
            db.query(ScadaEvent)
            .filter(
                ScadaEvent.lagoon_id == lagoon_id,
                ScadaEvent.tag_id.in_(normalized_tag_ids),
            )
        )
        if at_or_before is not None:
            query = query.filter(ScadaEvent.start_ts <= at_or_before)

        rows = (
            query.order_by(
                ScadaEvent.tag_id.asc(),
                ScadaEvent.start_ts.desc(),
                ScadaEvent.created_at.desc(),
            )
            .distinct(ScadaEvent.tag_id)
            .all()
        )

        return {
            row.tag_id: row
            for row in rows
            if row.tag_id is not None
        }

    @staticmethod
    def get_active_alarms_map(
        db: Session,
        alarm_definition_ids: Iterable[object],
    ) -> dict[object, AlarmEvent]:
        """
        Retorna eventos OPEN por definicion en una sola consulta.
        """
        normalized_ids = [alarm_id for alarm_id in alarm_definition_ids if alarm_id is not None]
        if not normalized_ids:
            return {}

        rows = (
            db.query(AlarmEvent)
            .filter(
                AlarmEvent.alarm_definition_id.in_(normalized_ids),
                AlarmEvent.status == "OPEN",
            )
            .all()
        )

        return {
            row.alarm_definition_id: row
            for row in rows
        }

    @staticmethod
    def lock_definition(
        db: Session,
        definition_id,
    ) -> None:
        """
        Toma un lock a nivel de fila para serializar transiciones OPEN/CLOSE.
        """
        (
            db.query(AlarmDefinition.id)
            .filter(AlarmDefinition.id == definition_id)
            .with_for_update()
            .one()
        )

    @staticmethod
    def get_active_alarm(
        db: Session,
        alarm_definition_id,
    ) -> AlarmEvent | None:
        """Retorna el evento OPEN de una definicion, si existe."""
        return (
            db.query(AlarmEvent)
            .filter(
                AlarmEvent.alarm_definition_id == alarm_definition_id,
                AlarmEvent.status == "OPEN",
            )
            .order_by(AlarmEvent.opened_at.desc())
            .first()
        )

    @staticmethod
    def create_event(
        db: Session,
        definition: AlarmDefinition,
        opened_at: datetime,
        source_ts: datetime,
        open_value: str | None,
        open_reason: str | None,
    ) -> AlarmEvent:
        """Crea un evento de alarma OPEN para la definicion indicada."""
        event = AlarmEvent(
            alarm_definition_id=definition.id,
            lagoon_id=definition.lagoon_id,
            tag_id=definition.tag_id,
            alarm_type=definition.alarm_type,
            severity=definition.severity,
            status="OPEN",
            opened_at=opened_at,
            source_ts=source_ts,
            open_value=open_value,
            open_reason=open_reason,
            last_eval_ts=opened_at,
        )
        db.add(event)
        db.flush()
        return event

    @staticmethod
    def close_event(
        db: Session,
        event: AlarmEvent,
        closed_at: datetime,
        close_value: str | None,
        close_reason: str | None,
    ) -> AlarmEvent:
        """Cierra un evento OPEN y guarda su metadata de cierre."""
        duration_sec = int((closed_at - event.opened_at).total_seconds())
        event.status = "CLOSED"
        event.closed_at = closed_at
        event.duration_sec = max(duration_sec, 0)
        event.close_value = close_value
        event.close_reason = close_reason
        event.last_eval_ts = closed_at
        db.add(event)
        db.flush()
        return event

    @staticmethod
    def get_notification_rules(
        db: Session,
        definition: AlarmDefinition,
        transition: str,
    ) -> list[AlarmNotificationRule]:
        """
        Retorna reglas de notificacion candidatas para apertura de alarma.

        Arquitectura actual:
        - Notificar una sola vez por evento de alarma.
        - Solo se enruta cuando la transicion es OPEN.
        """
        if transition != "OPEN":
            return []

        query = (
            db.query(AlarmNotificationRule)
            .filter(
                AlarmNotificationRule.enabled.is_(True),
                or_(
                    AlarmNotificationRule.alarm_definition_id == definition.id,
                    and_(
                        AlarmNotificationRule.alarm_definition_id.is_(None),
                        AlarmNotificationRule.lagoon_id == definition.lagoon_id,
                    ),
                    and_(
                        AlarmNotificationRule.alarm_definition_id.is_(None),
                        AlarmNotificationRule.lagoon_id.is_(None),
                    ),
                ),
                or_(
                    AlarmNotificationRule.alarm_type.is_(None),
                    AlarmNotificationRule.alarm_type == definition.alarm_type,
                ),
                or_(
                    AlarmNotificationRule.severity.is_(None),
                    AlarmNotificationRule.severity == definition.severity,
                ),
            )
        )

        rules = query.all()
        return sorted(rules, key=_rule_specificity, reverse=True)


def _rule_specificity(rule: AlarmNotificationRule) -> tuple[int, int]:
    """Valores mas altos significan mayor precedencia en el enrutamiento."""
    has_definition = 1 if rule.alarm_definition_id else 0
    has_lagoon = 1 if rule.lagoon_id else 0
    return has_definition, has_lagoon


def deduplicate_rules(
    rules: Iterable[AlarmNotificationRule],
) -> list[AlarmNotificationRule]:
    """
    Elimina destinos duplicados preservando la precedencia del primer match.
    """
    seen: set[tuple[str, str]] = set()
    unique_rules: list[AlarmNotificationRule] = []

    for rule in rules:
        key = (rule.channel, rule.target)
        if key in seen:
            continue
        seen.add(key)
        unique_rules.append(rule)

    return unique_rules
