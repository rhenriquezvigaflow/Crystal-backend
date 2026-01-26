from sqlalchemy.orm import Session
from app.models.scada_event import ScadaEvent


class ScadaEventRepository:

    @staticmethod
    def open_event(
        db: Session,
        lagoon_id: str,
        tag_id: str,
        tag_label: str | None,
        start_ts,
    ):
        event = ScadaEvent(
            lagoon_id=lagoon_id,
            tag_id=tag_id,
            tag_label=tag_label,
            start_ts=start_ts,
        )
        db.add(event)

    @staticmethod
    def close_event(
        db: Session,
        lagoon_id: str,
        tag_id: str,
        end_ts,
    ):
        (
            db.query(ScadaEvent)
            .filter(
                ScadaEvent.lagoon_id == lagoon_id,
                ScadaEvent.tag_id == tag_id,
                ScadaEvent.end_ts.is_(None),
            )
            .update(
                {"end_ts": end_ts},
                synchronize_session=False,
            )
        )
