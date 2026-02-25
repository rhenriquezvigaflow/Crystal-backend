from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.scada_event_repository import ScadaEventRepository
from app.schemas.scada_event import LastPumpEventsResponse

router = APIRouter(prefix="/scada", tags=["SCADA Events"])


@router.get(
    "/{lagoon_id}/pump-events/last-3",
    response_model=LastPumpEventsResponse,
)
def get_last_3_pump_events(
    lagoon_id: str,
    db: Session = Depends(get_db),
):
    events = ScadaEventRepository.get_last_3_events_by_lagoon(
        db=db,
        lagoon_id=lagoon_id,
    )

    if not events:
        raise HTTPException(404, "No pump events")

    return {
        "lagoon_id": lagoon_id,
        "events": events,
    }
