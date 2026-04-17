from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.session import get_db
from app.schemas.scada_event import LastPumpEventsResponse
from app.security.rbac import ALL_READ_ROLES, require_roles
from app.services.scada_event_service import (
    get_last_3_pump_events,
    get_recent_events,
    get_recent_pump_events,
)
from app.services.scada_scope_service import ensure_scada_read_access

router = APIRouter(prefix="/scada", tags=["events"])
logger = get_logger("api.scada.events")


def _build_events_response(
    lagoon_id: str,
    events: list[dict],
) -> dict:
    return {
        "lagoon_id": lagoon_id,
        "events": events,
    }


@router.get("/{lagoon_id}/events", response_model=LastPumpEventsResponse)
def list_scada_events(
    lagoon_id: str,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles(ALL_READ_ROLES)),
):
    user_id, _roles = ensure_scada_read_access(
        db=db,
        user=user,
        lagoon_id=lagoon_id,
    )
    events = get_recent_events(
        db=db,
        lagoon_id=lagoon_id,
        limit=limit,
    )
    if not events:
        raise HTTPException(status_code=404, detail="No events found")

    logger.info(
        "[API] endpoint_response_summary endpoint=/scada/%s/events user_id=%s events_count=%s limit=%s",
        lagoon_id,
        user_id,
        len(events),
        limit,
    )
    return _build_events_response(lagoon_id, events)


@router.get("/{lagoon_id}/pump-events", response_model=LastPumpEventsResponse)
def list_scada_pump_events(
    lagoon_id: str,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles(ALL_READ_ROLES)),
):
    user_id, _roles = ensure_scada_read_access(
        db=db,
        user=user,
        lagoon_id=lagoon_id,
    )
    events = get_recent_pump_events(
        db=db,
        lagoon_id=lagoon_id,
        limit=limit,
    )
    if not events:
        raise HTTPException(status_code=404, detail="No pump events found")

    logger.info(
        "[API] endpoint_response_summary endpoint=/scada/%s/pump-events user_id=%s events_count=%s limit=%s",
        lagoon_id,
        user_id,
        len(events),
        limit,
    )
    return _build_events_response(lagoon_id, events)


@router.get(
    "/{lagoon_id}/pump-events/last-3",
    response_model=LastPumpEventsResponse,
)
def list_last_3_scada_pump_events(
    lagoon_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles(ALL_READ_ROLES)),
):
    user_id, _roles = ensure_scada_read_access(
        db=db,
        user=user,
        lagoon_id=lagoon_id,
    )
    events = get_last_3_pump_events(
        db=db,
        lagoon_id=lagoon_id,
    )
    if not events:
        raise HTTPException(status_code=404, detail="No pump events found")

    logger.info(
        "[API] endpoint_response_summary endpoint=/scada/%s/pump-events/last-3 user_id=%s events_count=%s",
        lagoon_id,
        user_id,
        len(events),
    )
    return _build_events_response(lagoon_id, events)
