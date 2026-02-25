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
            ORDER BY start_local
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
