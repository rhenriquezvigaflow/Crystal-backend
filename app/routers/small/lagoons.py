from datetime import datetime
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.jwt import get_current_user
from app.auth.services.lagoon_service import (
    PERMISSION_VIEW,
    ensure_lagoon_access,
    get_product_lagoons_for_user,
    resolve_permitted_product_types,
)
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.role import ProductType
from app.repositories.scada_event_repository import ScadaEventRepository
from app.scada.history.repo import get_history_rows
from app.schemas.scada import ScadaCurrent, ScadaSnapshot
from app.schemas.scada_event import LastPumpEventsResponse
from app.security.rbac import SMALL_READ_ROLES, extract_user_roles, require_roles
from app.services.scada_read_service import get_current, get_last_minute

router = APIRouter(
    prefix="/api/small",
    tags=["Small Lagoons"],
    dependencies=[Depends(require_roles(SMALL_READ_ROLES))],
)
logger = get_logger("api.small.lagoons")


def _extract_user_id(user: dict) -> str:
    user_id = user.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return user_id


@router.get("/lagoons")
def list_lagoons(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = _extract_user_id(user)
    email = str(user.get("email", "-"))
    roles = extract_user_roles(user)
    permitted_products = sorted(resolve_permitted_product_types(roles))

    lagoons = get_product_lagoons_for_user(
        db=db,
        user_id=user_id,
        user_roles=roles,
        product_type=ProductType.SMALL,
    )
    logger.info(
        "[LAGOONS] list_for_user endpoint=/api/small/lagoons user_id=%s email=%s roles=%s permitted_products=%s lagoons_count=%s",
        user_id,
        email,
        roles,
        permitted_products,
        len(lagoons),
    )

    return [
        {
            "id": lagoon.id,
            "name": lagoon.name,
            "plc_type": lagoon.plc_type,
            "timezone": lagoon.timezone,
            "product_type": "small",
        }
        for lagoon in lagoons
    ]


@router.get("/dashboard")
def small_dashboard(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = _extract_user_id(user)
    email = str(user.get("email", "-"))
    roles = extract_user_roles(user)
    lagoons = get_product_lagoons_for_user(
        db=db,
        user_id=user_id,
        user_roles=roles,
        product_type=ProductType.SMALL,
    )
    total = len(lagoons)
    logger.info(
        "[API] endpoint_response_summary endpoint=/api/small/dashboard user_id=%s email=%s roles=%s lagoons_total=%s",
        user_id,
        email,
        roles,
        total,
    )
    return {
        "product_type": "small",
        "lagoons_total": total,
    }


@router.get("/lagoons/{lagoon_id}/last-minute", response_model=ScadaSnapshot)
def small_last_minute(
    lagoon_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = _extract_user_id(user)
    email = str(user.get("email", "-"))
    roles = extract_user_roles(user)
    ensure_lagoon_access(
        db=db,
        user_id=user_id,
        user_email=email,
        user_roles=roles,
        lagoon_id=lagoon_id,
        permission=PERMISSION_VIEW,
        expected_product_type=ProductType.SMALL,
    )
    data = get_last_minute(lagoon_id, db)
    if not data:
        logger.warning(
            "[API] endpoint_response_summary endpoint=/api/small/lagoons/%s/last-minute user_id=%s result=no_data",
            lagoon_id,
            user_id,
        )
        raise HTTPException(404, "No data")
    logger.info(
        "[API] endpoint_response_summary endpoint=/api/small/lagoons/%s/last-minute user_id=%s tags_count=%s",
        lagoon_id,
        user_id,
        len(data.get("tags", {})),
    )
    return data


@router.get("/lagoons/{lagoon_id}/current", response_model=ScadaCurrent)
def small_current(
    lagoon_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = _extract_user_id(user)
    email = str(user.get("email", "-"))
    roles = extract_user_roles(user)
    ensure_lagoon_access(
        db=db,
        user_id=user_id,
        user_email=email,
        user_roles=roles,
        lagoon_id=lagoon_id,
        permission=PERMISSION_VIEW,
        expected_product_type=ProductType.SMALL,
    )
    data = get_current(lagoon_id, db)
    if not data:
        logger.warning(
            "[API] endpoint_response_summary endpoint=/api/small/lagoons/%s/current user_id=%s result=no_data",
            lagoon_id,
            user_id,
        )
        raise HTTPException(404, "No data")
    logger.info(
        "[API] endpoint_response_summary endpoint=/api/small/lagoons/%s/current user_id=%s tags_count=%s",
        lagoon_id,
        user_id,
        len(data.get("tags", {})),
    )
    return data


@router.get(
    "/lagoons/{lagoon_id}/pump-events/last-3",
    response_model=LastPumpEventsResponse,
)
def small_last_3_pump_events(
    lagoon_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = _extract_user_id(user)
    email = str(user.get("email", "-"))
    roles = extract_user_roles(user)
    ensure_lagoon_access(
        db=db,
        user_id=user_id,
        user_email=email,
        user_roles=roles,
        lagoon_id=lagoon_id,
        permission=PERMISSION_VIEW,
        expected_product_type=ProductType.SMALL,
    )
    events = ScadaEventRepository.get_last_3_events_by_lagoon(
        db=db,
        lagoon_id=lagoon_id,
    )

    if not events:
        logger.warning(
            "[API] endpoint_response_summary endpoint=/api/small/lagoons/%s/pump-events/last-3 user_id=%s result=no_events",
            lagoon_id,
            user_id,
        )
        raise HTTPException(404, "No pump events")
    logger.info(
        "[API] endpoint_response_summary endpoint=/api/small/lagoons/%s/pump-events/last-3 user_id=%s events_count=%s",
        lagoon_id,
        user_id,
        len(events),
    )

    return {
        "lagoon_id": lagoon_id,
        "events": events,
    }


@router.get("/history")
def small_history(
    lagoon_id: str = Query(...),
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    resolution: Optional[Literal["hourly", "daily", "weekly"]] = Query(None),
    tags: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    user_id = _extract_user_id(user)
    email = str(user.get("email", "-"))
    roles = extract_user_roles(user)
    ensure_lagoon_access(
        db=db,
        user_id=user_id,
        user_email=email,
        user_roles=roles,
        lagoon_id=lagoon_id,
        permission=PERMISSION_VIEW,
        expected_product_type=ProductType.SMALL,
    )
    data = get_history_rows(
        db=db,
        lagoon_id=lagoon_id,
        start_date=start_date,
        end_date=end_date,
        resolution=resolution,
        tags=tags,
    )

    series_map: Dict[str, list] = {}

    for row in data["rows"]:
        tag = row["tag_id"]
        series_map.setdefault(tag, []).append(
            {
                "timestamp": row["bucket"],
                "value": float(row["avg_val"]) if row["avg_val"] is not None else None,
            }
        )

    response = {
        "lagoon_id": lagoon_id,
        "resolution": data["resolution"],
        "source": data["source"],
        "series": [
            {"tag": tag, "points": points}
            for tag, points in series_map.items()
        ],
    }
    logger.info(
        "[API] endpoint_response_summary endpoint=/api/small/history user_id=%s lagoon_id=%s resolution=%s tags_requested=%s series_count=%s source=%s",
        user_id,
        lagoon_id,
        response["resolution"],
        len(tags or []),
        len(response["series"]),
        response["source"],
    )
    return response
