from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.lagoon import Lagoon
from app.models.role import ProductType
from app.repositories.scada_event_repository import ScadaEventRepository
from app.scada.history.repo import get_history_rows
from app.schemas.scada import ScadaCurrent, ScadaSnapshot
from app.schemas.scada_event import LastPumpEventsResponse
from app.security.rbac import SMALL_READ_ROLES, require_roles
from app.services.scada_read_service import get_current, get_last_minute

router = APIRouter(
    prefix="/api/small",
    tags=["Small Lagoons"],
    dependencies=[Depends(require_roles(SMALL_READ_ROLES))],
)


@router.get("/lagoons")
def list_lagoons(db: Session = Depends(get_db)):
    lagoons = (
        db.query(Lagoon)
        .filter(Lagoon.product_type == ProductType.SMALL)
        .order_by(Lagoon.name.asc())
        .all()
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
def small_dashboard(db: Session = Depends(get_db)):
    total = (
        db.query(Lagoon)
        .filter(Lagoon.product_type == ProductType.SMALL)
        .count()
    )
    return {
        "product_type": "small",
        "lagoons_total": total,
    }


@router.get("/lagoons/{lagoon_id}/last-minute", response_model=ScadaSnapshot)
def small_last_minute(lagoon_id: str, db: Session = Depends(get_db)):
    data = get_last_minute(lagoon_id, db)
    if not data:
        raise HTTPException(404, "No data")
    return data


@router.get("/lagoons/{lagoon_id}/current", response_model=ScadaCurrent)
def small_current(lagoon_id: str, db: Session = Depends(get_db)):
    data = get_current(lagoon_id, db)
    if not data:
        raise HTTPException(404, "No data")
    return data


@router.get(
    "/lagoons/{lagoon_id}/pump-events/last-3",
    response_model=LastPumpEventsResponse,
)
def small_last_3_pump_events(
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


@router.get("/history")
def small_history(
    lagoon_id: str = Query(...),
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    resolution: Optional[str] = Query(None),  # hourly | daily | weekly
    tags: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db),
):
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

    return {
        "lagoon_id": lagoon_id,
        "resolution": data["resolution"],
        "source": data["source"],
        "series": [
            {"tag": tag, "points": points}
            for tag, points in series_map.items()
        ],
    }
