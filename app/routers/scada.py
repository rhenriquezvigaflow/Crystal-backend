from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.session import get_db
from app.schemas.scada import ScadaCurrent, ScadaKpis
from app.security.rbac import ALL_READ_ROLES, require_roles
from app.services.scada_query_service import (
    get_history_payload,
    get_kpis_payload,
    get_realtime_payload,
)
from app.services.scada_scope_service import ensure_scada_read_access

router = APIRouter(prefix="/scada", tags=["scada"])
logger = get_logger("api.scada")


@router.get("/{lagoon_id}/realtime", response_model=ScadaCurrent)
def get_scada_realtime(
    lagoon_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles(ALL_READ_ROLES)),
):
    user_id, _roles = ensure_scada_read_access(
        db=db,
        user=user,
        lagoon_id=lagoon_id,
    )
    data = get_realtime_payload(
        db=db,
        lagoon_id=lagoon_id,
        state_store=getattr(request.app.state, "state_store", None),
    )
    if not data:
        raise HTTPException(status_code=404, detail="SCADA realtime not found")

    logger.info(
        "[API] endpoint_response_summary endpoint=/scada/%s/realtime user_id=%s tags_count=%s",
        lagoon_id,
        user_id,
        len(data.get("tags", {})),
    )
    return data


@router.get("/{lagoon_id}/history")
def get_scada_history(
    lagoon_id: str,
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    resolution: Literal["hourly", "daily", "weekly"] = Query("hourly"),
    tags: list[str] | None = Query(None),
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles(ALL_READ_ROLES)),
):
    user_id, roles = ensure_scada_read_access(
        db=db,
        user=user,
        lagoon_id=lagoon_id,
    )
    response = get_history_payload(
        db=db,
        lagoon_id=lagoon_id,
        start_date=start_date,
        end_date=end_date,
        resolution=resolution,
        tags=tags,
    )
    logger.info(
        "[API] endpoint_response_summary endpoint=/scada/%s/history user_id=%s roles=%s resolution=%s tags_requested=%s series_count=%s source=%s",
        lagoon_id,
        user_id,
        roles,
        response["resolution"],
        len(tags or []),
        len(response["series"]),
        response["source"],
    )
    return response


@router.get("/{lagoon_id}/kpis", response_model=ScadaKpis)
def get_scada_kpis(
    lagoon_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles(ALL_READ_ROLES)),
):
    user_id, _roles = ensure_scada_read_access(
        db=db,
        user=user,
        lagoon_id=lagoon_id,
    )
    state_store = getattr(request.app.state, "state_store", None)
    data = get_kpis_payload(
        db=db,
        lagoon_id=lagoon_id,
        state_store=state_store,
    )
    if not data:
        raise HTTPException(status_code=404, detail="SCADA KPIs not found")

    logger.info(
        "[API] endpoint_response_summary endpoint=/scada/%s/kpis user_id=%s tags_count=%s pump_events_count=%s",
        lagoon_id,
        user_id,
        data.get("tags_count", 0),
        data.get("pump_events_count", 0),
    )
    return data
