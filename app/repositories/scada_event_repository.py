from sqlalchemy.orm import Session
from sqlalchemy import text


class ScadaEventRepository:
    
    @staticmethod
    def get_last_event_time_by_lagoon(db: Session, lagoon_id: str) -> dict[str, str]:

        sql = text("""
            SELECT 
                lagoon_id, 
                tag_id,
                tag_label,
                start_local
            FROM vw_scada_last_3_pump_actions
            WHERE lagoon_id = :lagoon_id
            ORDER BY start_local DESC
        """)

        rows = db.execute(sql, {"lagoon_id": lagoon_id}).fetchall()

        latest_by_tag: dict[str, str] = {}
        for row in rows:
            if not row.start_local:
                continue
            start_local = (
                row.start_local.isoformat()
                if hasattr(row.start_local, "isoformat")
                else str(row.start_local)
            )
            # Con ORDER BY DESC preservamos el más reciente por tag.
            latest_by_tag.setdefault(
                row.tag_id,
                start_local,
            )

        return latest_by_tag

    @staticmethod
    def get_last_3_events_by_lagoon(db: Session, lagoon_id: str) -> list[dict]:
        sql = text("""
            SELECT
                lagoon_id,
                tag_id,
                tag_label,
                start_local
            FROM vw_scada_last_3_pump_actions
            WHERE lagoon_id = :lagoon_id
            ORDER BY start_local DESC
        """)

        rows = db.execute(sql, {"lagoon_id": lagoon_id}).mappings().all()

        events: list[dict] = []
        for row in rows:
            start_local = (
                row["start_local"].isoformat()
                if hasattr(row["start_local"], "isoformat")
                else str(row["start_local"])
            )
            events.append(
                {
                    "lagoon_id": row["lagoon_id"],
                    "tag_id": row["tag_id"],
                    "tag_label": row["tag_label"],
                    "start_local": start_local,
                }
            )

        return events

    @staticmethod
    def get_recent_events_by_lagoon(
        db: Session,
        lagoon_id: str,
        limit: int = 100,
    ) -> list[dict]:
        safe_limit = max(1, min(int(limit), 500))
        sql = text("""
            SELECT
                lagoon_id,
                tag_id,
                tag_label,
                start_ts AS start_local
            FROM scada_event
            WHERE lagoon_id = :lagoon_id
              AND start_ts IS NOT NULL
            ORDER BY start_ts DESC
            LIMIT :limit
        """)

        rows = db.execute(
            sql,
            {"lagoon_id": lagoon_id, "limit": safe_limit},
        ).mappings().all()

        events: list[dict] = []
        for row in rows:
            start_local = (
                row["start_local"].isoformat()
                if hasattr(row["start_local"], "isoformat")
                else str(row["start_local"])
            )
            events.append(
                {
                    "lagoon_id": row["lagoon_id"],
                    "tag_id": row["tag_id"],
                    "tag_label": row["tag_label"],
                    "start_local": start_local,
                }
            )

        return events

    @staticmethod
    def get_event_report_by_lagoon_name(
        db: Session,
        lagoon_name: str,
    ) -> tuple[list[str], list[dict]]:
        sql = text("""
            SELECT
                nombre_laguna AS "Lagoon",
                nombre_bomba AS "Pump",
                name_tag AS "Tag Name",
                estado_codigo AS "State Code",
                CASE estado_codigo
                    WHEN 0 THEN 'Stopped'
                    WHEN 1 THEN 'Running'
                    WHEN 3 THEN 'Fault'
                    ELSE COALESCE(NULLIF(estado_nombre, ''), 'Unknown')
                END AS "State",
                hora_inicio_planta AS "Plant Start Time",
                hora_termino_planta AS "Plant End Time",
                tiempo_ejecucion AS "Runtime"
            FROM public.vw_scada_event_report
            WHERE estado_codigo NOT IN (2)
              AND nombre_laguna = :lagoon_name
              AND (
                  tiempo_ejecucion IS NULL
                  OR tiempo_ejecucion !~ '-'
              )
            ORDER BY nombre_laguna, nombre_bomba, hora_inicio_planta
        """)

        result = db.execute(sql, {"lagoon_name": lagoon_name})
        columns = list(result.keys())
        rows = [dict(row) for row in result.mappings().all()]

        return columns, rows
