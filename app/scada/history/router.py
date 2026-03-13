from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional, Dict

from app.db.session import get_db
from app.scada.history.repo import get_history_rows
from app.security.rbac import ALL_READ_ROLES, require_roles


router = APIRouter(
    prefix="/scada/history",
    tags=["SCADA History"],
)

@router.get("/{resolution}")
def get_history(
    resolution: str,  # hourly | daily | weekly 
    lagoon_id: str = Query(...),
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    tags: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db),
    _user: dict = Depends(require_roles(ALL_READ_ROLES)),
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

    for r in data["rows"]:
        tag = r["tag_id"]
        series_map.setdefault(tag, []).append({
            "timestamp": r["bucket"],
            "value": float(r["avg_val"]) if r["avg_val"] is not None else None,
        })

    return {
        "lagoon_id": lagoon_id,
        "resolution": data["resolution"],
        "source": data["source"],
        "series": [
            {"tag": tag, "points": points}
            for tag, points in series_map.items()
        ],
    }
