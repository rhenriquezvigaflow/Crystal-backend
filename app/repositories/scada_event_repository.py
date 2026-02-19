from sqlalchemy.orm import Session
from sqlalchemy import text


class ScadaEventRepository:
    
    @staticmethod
    def get_last_event_time_by_lagoon(db: Session, lagoon_id: str) -> dict[str, str]:

        sql = text("""
            SELECT DISTINCT ON (e.lagoon_id, e.tag_id)
                e.tag_id,
                (e.start_ts AT TIME ZONE l.timezone) AS start_local
            FROM scada_event e
            JOIN lagoons l ON l.id = e.lagoon_id
            WHERE 
                e.lagoon_id = :lagoon_id
                AND e.state = 1
            ORDER BY 
                e.lagoon_id, 
                e.tag_id, 
                e.start_ts DESC;
        """)

        rows = db.execute(sql, {"lagoon_id": lagoon_id}).fetchall()

        return {
            row.tag_id: row.start_local.isoformat()
            for row in rows
            if row.start_local
        }