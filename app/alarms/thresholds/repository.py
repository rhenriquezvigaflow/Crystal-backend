from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.alarms.models import AlarmDefinition


class AlarmThresholdRepository:
    """Acceso a datos para alarmas de umbral PT/FIT."""

    @staticmethod
    def get_threshold_rows_view(
        db: Session,
        lagoon_id: str,
    ) -> list[dict]:
        rows = db.execute(
            text(
                """
                WITH threshold_defs AS (
                    SELECT
                        upper(d.tag_id) AS tag_id,
                        bool_and(COALESCE(d.enabled, true)) AS enabled,
                        max(
                            CASE
                                WHEN lower(COALESCE(d.condition ->> 'mode', '')) = 'min'
                                    OR (d.condition ->> 'op') IN ('<', '<=')
                                THEN NULLIF(d.condition ->> 'value', '')::double precision
                                ELSE NULL
                            END
                        ) AS min_value,
                        max(
                            CASE
                                WHEN lower(COALESCE(d.condition ->> 'mode', '')) = 'max'
                                    OR (d.condition ->> 'op') IN ('>', '>=')
                                THEN NULLIF(d.condition ->> 'value', '')::double precision
                                ELSE NULL
                            END
                        ) AS max_value,
                        max(
                            CASE lower(COALESCE(d.severity, 'warning'))
                                WHEN 'critical' THEN 3
                                WHEN 'warning' THEN 2
                                WHEN 'info' THEN 1
                                ELSE 2
                            END
                        ) AS severity_rank
                    FROM alarm_definition d
                    WHERE
                        d.lagoon_id = :lagoon_id
                        AND d.alarm_type = 'threshold'
                        AND d.tag_id IS NOT NULL
                        AND (
                            upper(d.tag_id) LIKE 'PT%%'
                            OR upper(d.tag_id) LIKE 'FIT%%'
                        )
                    GROUP BY upper(d.tag_id)
                ),
                minute_tags AS (
                    SELECT DISTINCT
                        upper(m.tag_id) AS tag_id,
                        NULL::text AS tag_name
                    FROM scada_minute m
                    WHERE
                        m.lagoon_id = :lagoon_id
                        AND m.tag_id IS NOT NULL
                        AND (
                            upper(m.tag_id) LIKE 'PT%%'
                            OR upper(m.tag_id) LIKE 'FIT%%'
                        )
                ),
                event_tags AS (
                    SELECT
                        upper(e.tag_id) AS tag_id,
                        max(NULLIF(btrim(e.tag_label), '')) AS tag_name
                    FROM scada_event e
                    WHERE
                        e.lagoon_id = :lagoon_id
                        AND e.tag_id IS NOT NULL
                        AND (
                            upper(e.tag_id) LIKE 'PT%%'
                            OR upper(e.tag_id) LIKE 'FIT%%'
                        )
                    GROUP BY upper(e.tag_id)
                ),
                candidate_tags AS (
                    SELECT
                        mt.tag_id,
                        mt.tag_name
                    FROM minute_tags mt
                    UNION
                    SELECT
                        et.tag_id,
                        et.tag_name
                    FROM event_tags et
                ),
                candidate_by_tag AS (
                    SELECT
                        ct.tag_id,
                        max(ct.tag_name) AS tag_name
                    FROM candidate_tags ct
                    GROUP BY ct.tag_id
                ),
                tag_universe AS (
                    SELECT tag_id FROM threshold_defs
                    UNION
                    SELECT tag_id FROM candidate_by_tag
                )
                SELECT
                    :lagoon_id AS lagoon_id,
                    t.tag_id,
                    COALESCE(cbt.tag_name, t.tag_id) AS tag_name,
                    CASE
                        WHEN td.tag_id IS NOT NULL THEN 'configured'
                        ELSE 'candidate'
                    END AS source,
                    td.min_value,
                    td.max_value,
                    CASE COALESCE(td.severity_rank, 2)
                        WHEN 3 THEN 'critical'
                        WHEN 2 THEN 'warning'
                        WHEN 1 THEN 'info'
                        ELSE 'warning'
                    END AS severity,
                    COALESCE(td.enabled, true) AS enabled
                FROM tag_universe t
                LEFT JOIN threshold_defs td
                    ON td.tag_id = t.tag_id
                LEFT JOIN candidate_by_tag cbt
                    ON cbt.tag_id = t.tag_id
                ORDER BY t.tag_id ASC
                """
            ),
            {"lagoon_id": lagoon_id},
        ).mappings().all()

        return [dict(row) for row in rows]

    @staticmethod
    def get_definition_by_code(
        db: Session,
        lagoon_id: str,
        code: str,
    ) -> AlarmDefinition | None:
        return (
            db.query(AlarmDefinition)
            .filter(
                AlarmDefinition.lagoon_id == lagoon_id,
                AlarmDefinition.code == code,
            )
            .first()
        )

    @staticmethod
    def save_definition(
        db: Session,
        definition: AlarmDefinition,
    ) -> None:
        db.add(definition)
        db.flush()
