from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Literal, Dict, Any

from sqlalchemy import text
from sqlalchemy.orm import Session

Resolution = Literal["hourly", "daily", "weekly"]


@dataclass(frozen=True)
class ResolutionChoice:
    key: Resolution
    view: str
    bucket: str
    label: str


RESOLUTIONS: List[ResolutionChoice] = [
    ResolutionChoice("hourly", "public.scada_minute_hourly", "1 hour", "1h"),
    ResolutionChoice("daily",  "public.scada_minute_daily",  "1 day",  "1d"),
    ResolutionChoice("weekly", "public.scada_minute_weekly", "1 week", "1w"),
]


def table_exists(db: Session, qualified_name: str) -> bool:
    row = db.execute(
        text("SELECT to_regclass(:name) AS oid"),
        {"name": qualified_name},
    ).mappings().first()
    return bool(row and row["oid"])


# 🔹 REGLA DE NEGOCIO DEFINITIVA
def pick_resolution_by_days(days: float) -> ResolutionChoice:
    if days <= 7:
        return RESOLUTIONS[0]   # hourly
    if days <= 90:
        return RESOLUTIONS[1]   # daily
    return RESOLUTIONS[2]       # weekly


def fetch_from_view(
    db: Session,
    view: str,
    lagoon_id: str,
    start_date: datetime,
    end_date: datetime,
    tags: Optional[List[str]],
):
    where_tags = ""
    params = {
        "lagoon_id": lagoon_id,
        "start": start_date,
        "end": end_date,
    }

    if tags:
        where_tags = "AND tag_id = ANY(:tags)"
        params["tags"] = tags

    sql = text(f"""
        SELECT
            bucket,
            lagoon_id,
            tag_id,
            avg_val
        FROM {view}
        WHERE lagoon_id = :lagoon_id
          AND bucket BETWEEN :start AND :end
          {where_tags}
        ORDER BY bucket
    """)

    return db.execute(sql, params).mappings().all()


def fetch_fallback_timebucket(
    db: Session,
    bucket: str,
    lagoon_id: str,
    start_date: datetime,
    end_date: datetime,
    tags: Optional[List[str]],
):
    where_tags = ""
    params = {
        "lagoon_id": lagoon_id,
        "start": start_date,
        "end": end_date,
    }

    if tags:
        where_tags = "AND tag_id = ANY(:tags)"
        params["tags"] = tags

    sql = text(f"""
        SELECT
            time_bucket('{bucket}', bucket_ts) AS bucket,
            lagoon_id,
            tag_id,
            AVG(value_num) AS avg_val
        FROM public.scada_minute
        WHERE lagoon_id = :lagoon_id
          AND bucket_ts BETWEEN :start AND :end
          AND value_num IS NOT NULL
          {where_tags}
        GROUP BY 1,2,3
        ORDER BY bucket
    """)

    return db.execute(sql, params).mappings().all()


def get_history_rows(
    db: Session,
    lagoon_id: str,
    start_date: datetime,
    end_date: datetime,
    resolution: Optional[str],   # ← se ignora, queda solo por compatibilidad
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:

    days = (end_date - start_date).total_seconds() / 86400.0
    res = pick_resolution_by_days(days)

    if table_exists(db, res.view):
        rows = fetch_from_view(
            db,
            res.view,
            lagoon_id,
            start_date,
            end_date,
            tags,
        )
        source = "view"
    else:
        rows = fetch_fallback_timebucket(
            db,
            res.bucket,
            lagoon_id,
            start_date,
            end_date,
            tags,
        )
        source = "table"

    return {
        "rows": rows,
        "resolution": res.key,   # hourly | daily | weekly
        "source": source,
    }
