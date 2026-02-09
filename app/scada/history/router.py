from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional, Dict

from app.db.session import SessionLocal
from app.scada.history.repo import get_history_rows


router = APIRouter(
    prefix="/scada/history",
    tags=["SCADA History"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/{resolution}")
def get_history(
    resolution: str,  # hourly | daily | weekly (informativo)
    lagoon_id: str = Query(...),
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
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
