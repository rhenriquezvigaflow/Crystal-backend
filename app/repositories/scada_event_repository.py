from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.scada_event import ScadaEvent


class ScadaEventRepository:

    @staticmethod
    def get_last_start_ts_by_lagoon(db: Session, lagoon_id: str) -> dict[str, str]:
        """
        Devuelve el último start_ts por tag_id.
        """
        rows = (
            db.query(
                ScadaEvent.tag_id,
                func.max(ScadaEvent.start_ts).label("start_ts"),
            )
            .filter(ScadaEvent.lagoon_id == lagoon_id)
            .group_by(ScadaEvent.tag_id)
            .all()
        )

        return {
            row.tag_id: row.start_ts.isoformat()
            for row in rows
            if row.start_ts
        }
