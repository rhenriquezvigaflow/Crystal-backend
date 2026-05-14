from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.alarms.models import ALARM_TYPE_THRESHOLD, AlarmDefinition
from app.alarms.thresholds.repository import AlarmThresholdRepository
from app.alarms.thresholds.schemas import (
    ThresholdConfigRequest,
    ThresholdViewRowOut,
)
from app.core.lagoon_aliases import normalize_lagoon_id
from app.core.logging import get_logger

logger = get_logger("alarms.thresholds.service")


class AlarmThresholdService:
    """Logica de negocio para alarmas de umbral PT/FIT."""

    @staticmethod
    def get_thresholds_view(
        db: Session,
        lagoon_id: str,
    ) -> list[ThresholdViewRowOut]:
        canonical_lagoon_id = normalize_lagoon_id(lagoon_id)
        rows = AlarmThresholdRepository.get_threshold_rows_view(
            db=db,
            lagoon_id=canonical_lagoon_id,
        )
        return [ThresholdViewRowOut(**row) for row in rows]

    @staticmethod
    def upsert_thresholds(
        db: Session,
        lagoon_id: str,
        payload: ThresholdConfigRequest,
    ) -> tuple[list[str], list[str]]:
        canonical_lagoon_id = normalize_lagoon_id(lagoon_id)
        created_codes: list[str] = []
        updated_codes: list[str] = []

        for item in payload.items:
            tag_id = item.tag_id

            if item.max_value is not None:
                status, code = AlarmThresholdService._upsert_one(
                    db=db,
                    lagoon_id=canonical_lagoon_id,
                    tag_id=tag_id,
                    side="max",
                    limit_value=float(item.max_value),
                    severity=item.severity,
                    enabled=item.enabled,
                )
                if status == "created":
                    created_codes.append(code)
                else:
                    updated_codes.append(code)

            if item.min_value is not None:
                status, code = AlarmThresholdService._upsert_one(
                    db=db,
                    lagoon_id=canonical_lagoon_id,
                    tag_id=tag_id,
                    side="min",
                    limit_value=float(item.min_value),
                    severity=item.severity,
                    enabled=item.enabled,
                )
                if status == "created":
                    created_codes.append(code)
                else:
                    updated_codes.append(code)

        return created_codes, updated_codes

    @staticmethod
    def _upsert_one(
        db: Session,
        *,
        lagoon_id: str,
        tag_id: str,
        side: str,
        limit_value: float,
        severity: str,
        enabled: bool,
    ) -> tuple[str, str]:
        if side == "max":
            code = f"threshold_{tag_id.lower()}_max"
            op = ">"
            name = f"{tag_id} max threshold"
            description = (
                f"Alarma de umbral maximo para {tag_id}. "
                f"Se activa cuando el valor supera {limit_value}."
            )
        elif side == "min":
            code = f"threshold_{tag_id.lower()}_min"
            op = "<"
            name = f"{tag_id} min threshold"
            description = (
                f"Alarma de umbral minimo para {tag_id}. "
                f"Se activa cuando el valor cae por debajo de {limit_value}."
            )
        else:
            raise ValueError(f"Unsupported side '{side}' for tag '{tag_id}'")

        definition = AlarmThresholdRepository.get_definition_by_code(
            db=db,
            lagoon_id=lagoon_id,
            code=code,
        )
        created = definition is None

        if definition is None:
            definition = AlarmDefinition(
                lagoon_id=lagoon_id,
                tag_id=tag_id,
                code=code,
                alarm_type=ALARM_TYPE_THRESHOLD,
            )

        definition.tag_id = tag_id
        definition.name = name
        definition.description = description
        definition.severity = severity
        definition.enabled = enabled
        definition.condition = {
            "op": op,
            "value": float(limit_value),
            "mode": side,
        }
        definition.deadband = 0.0

        AlarmThresholdRepository.save_definition(
            db=db,
            definition=definition,
        )

        logger.info(
            "[THRESHOLD UPSERT] lagoon_id=%s tag_id=%s side=%s code=%s status=%s",
            lagoon_id,
            tag_id,
            side,
            code,
            "created" if created else "updated",
        )
        return ("created" if created else "updated"), code

    @staticmethod
    def log_exception(
        *,
        action: str,
        lagoon_id: str,
        tag_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        logger.exception(
            "[THRESHOLD ERROR] action=%s lagoon_id=%s tag_id=%s extra=%s",
            action,
            lagoon_id,
            tag_id,
            extra or {},
        )
