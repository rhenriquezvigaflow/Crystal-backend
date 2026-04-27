from __future__ import annotations

from datetime import datetime
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.session import get_db
from app.models.lagoon import Lagoon
from app.repositories.scada_event_repository import ScadaEventRepository
from app.schemas.scada_event import LastPumpEventsResponse
from app.security.rbac import ALL_READ_ROLES, require_roles
from app.services.scada_event_service import (
    get_last_3_pump_events,
    get_recent_events,
    get_recent_pump_events,
)
from app.services.scada_scope_service import ensure_scada_read_access
from app.services.xlsx_export import XLSX_MEDIA_TYPE, build_xlsx_workbook

router = APIRouter(prefix="/scada", tags=["events"])
logger = get_logger("api.scada.events")


def _slugify_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "laguna"


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


@router.get("/{lagoon_id}/pump-events/report.xlsx")
def download_pump_events_report(
    lagoon_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles(ALL_READ_ROLES)),
):
    user_id, _roles = ensure_scada_read_access(
        db=db,
        user=user,
        lagoon_id=lagoon_id,
    )
    lagoon = db.get(Lagoon, lagoon_id)
    lagoon_name = lagoon.name if lagoon and lagoon.name else lagoon_id

    columns, rows = ScadaEventRepository.get_event_report_by_lagoon_name(
        db=db,
        lagoon_name=lagoon_name,
    )
    workbook = build_xlsx_workbook(
        columns=columns,
        rows=rows,
        sheet_name="Pump Report",
    )
    filename = (
        f"pump_report_{_slugify_filename(lagoon_name)}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )

    logger.info(
        "[API] endpoint_response_summary endpoint=/scada/%s/pump-events/report.xlsx user_id=%s rows_count=%s",
        lagoon_id,
        user_id,
        len(rows),
    )
    return Response(
        content=workbook,
        media_type=XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
