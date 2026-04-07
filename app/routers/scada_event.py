from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.services.lagoon_service import PERMISSION_VIEW, ensure_lagoon_access
from app.core.logging import get_logger
from app.db.session import get_db
from app.repositories.scada_event_repository import ScadaEventRepository
from app.schemas.scada_event import LastPumpEventsResponse
from app.security.rbac import ALL_READ_ROLES, extract_user_roles, require_roles

router = APIRouter(prefix="/scada", tags=["SCADA Events"])
logger = get_logger("api.scada.events")


def _extract_user_id(user: dict) -> str:
    user_id = user.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return user_id


@router.get(
    "/{lagoon_id}/pump-events/last-3",
    response_model=LastPumpEventsResponse,
)
def get_last_3_pump_events(
    lagoon_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles(ALL_READ_ROLES)),
):
    user_id = _extract_user_id(user)
    ensure_lagoon_access(
        db=db,
        user_id=user_id,
        user_email=str(user.get("email", "-")),
        user_roles=extract_user_roles(user),
        lagoon_id=lagoon_id,
        permission=PERMISSION_VIEW,
    )
    events = ScadaEventRepository.get_last_3_events_by_lagoon(
        db=db,
        lagoon_id=lagoon_id,
    )

    if not events:
        raise HTTPException(404, "No pump events")
    logger.info(
        "[API] endpoint_response_summary endpoint=/scada/%s/pump-events/last-3 user_id=%s events_count=%s",
        lagoon_id,
        user_id,
        len(events),
    )

    return {
        "lagoon_id": lagoon_id,
        "events": events,
    }
