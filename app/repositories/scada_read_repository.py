from sqlalchemy.orm import Session
from sqlalchemy import func, distinct
from app.models.scada_minute import ScadaMinute


class ScadaReadRepository:

    @staticmethod
    def get_last_minute(db: Session, lagoon_id: str):
        last_bucket = (
            db.query(func.max(ScadaMinute.bucket))
            .filter(ScadaMinute.lagoon_id == lagoon_id)
            .scalar()
        )

        if not last_bucket:
            return None, None

        rows = (
            db.query(ScadaMinute)
            .filter(
                ScadaMinute.lagoon_id == lagoon_id,
                ScadaMinute.bucket == last_bucket,
            )
            .all()
        )

        return last_bucket, rows

    @staticmethod
    def get_current(db: Session, lagoon_id: str):
        rows = (
            db.query(ScadaMinute)
            .distinct(ScadaMinute.tag_id)
            .filter(ScadaMinute.lagoon_id == lagoon_id)
            .order_by(
                ScadaMinute.tag_id,
                ScadaMinute.bucket.desc(),
            )
            .all()
        )

        return rows
