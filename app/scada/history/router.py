# app/scada/history/router.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional, Dict

from app.db.session import SessionLocal
from .repo import get_hourly_history
from .schemas import HistoryHourlyResponse, HistorySeries, HistoryPoint

router = APIRouter(prefix="/scada/history", tags=["SCADA History"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/hourly", response_model=HistoryHourlyResponse)
def get_history_hourly(
    lagoon_id: str = Query(...),
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    tags: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db),
):
    rows = get_hourly_history(
        db=db,
        lagoon_id=lagoon_id,
        start_date=start_date,
        end_date=end_date,
        tags=tags,
    )

    series_map: Dict[str, HistorySeries] = {}

    for r in rows:
        tag = r.tag_id

        if tag not in series_map:
            # ⚠️ metadata mínima (como IDA)
            series_map[tag] = HistorySeries(
                tag_key=tag,
                name=tag,        # luego puedes mapear a nombre humano
                unit=None,
                decimals=2,
                points=[],
            )

        if r.value_num is not None:
            value = float(r.value_num)
        elif r.value_bool is not None:
            value = 1.0 if r.value_bool else 0.0
        else:
            continue

        series_map[tag].points.append(
            HistoryPoint(
                timestamp=r.bucket_ts,
                value=round(value, series_map[tag].decimals),
            )
        )

    return HistoryHourlyResponse(
        lagoon_id=lagoon_id,
        series=list(series_map.values()),
    )
