from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Literal, Dict, Any, cast

from sqlalchemy import text
from sqlalchemy.orm import Session

Resolution = Literal["hourly", "daily", "weekly"]


@dataclass(frozen=True)
class ResolutionChoice:
    key: Resolution
    view: str
    label: str


RESOLUTIONS: List[ResolutionChoice] = [
    # Vistas creadas por scripts/sql/create_scada_continuous_aggregates.sql
    ResolutionChoice("hourly", "public.scada_minute_hourly", "1h"),
    ResolutionChoice("daily", "public.scada_minute_daily", "1d"),
    ResolutionChoice("weekly", "public.scada_minute_weekly", "1w"),
]

RESOLUTION_BY_KEY: Dict[Resolution, ResolutionChoice] = {
    r.key: r for r in RESOLUTIONS
}

VIEW_QUERY_BY_KEY: Dict[Resolution, Any] = {
    "hourly": text(
        """
        SELECT
            bucket,
            lagoon_id,
            tag_id,
            avg_val
        FROM public.scada_minute_hourly
        WHERE lagoon_id = :lagoon_id
          AND bucket BETWEEN :start AND :end
          AND (:use_tags = FALSE OR tag_id = ANY(:tags))
        ORDER BY bucket
        """
    ),
    "daily": text(
        """
        SELECT
            bucket,
            lagoon_id,
            tag_id,
            avg_val
        FROM public.scada_minute_daily
        WHERE lagoon_id = :lagoon_id
          AND bucket BETWEEN :start AND :end
          AND (:use_tags = FALSE OR tag_id = ANY(:tags))
        ORDER BY bucket
        """
    ),
    "weekly": text(
        """
        SELECT
            bucket,
            lagoon_id,
            tag_id,
            avg_val
        FROM public.scada_minute_weekly
        WHERE lagoon_id = :lagoon_id
          AND bucket BETWEEN :start AND :end
          AND (:use_tags = FALSE OR tag_id = ANY(:tags))
        ORDER BY bucket
        """
    ),
}

FALLBACK_QUERY_BY_KEY: Dict[Resolution, Any] = {
    "hourly": text(
        """
        SELECT
            time_bucket('1 hour', bucket_ts) AS bucket,
            lagoon_id,
            tag_id,
            AVG(value_num) AS avg_val
        FROM public.scada_minute
        WHERE lagoon_id = :lagoon_id
          AND bucket_ts BETWEEN :start AND :end
          AND value_num IS NOT NULL
          AND (:use_tags = FALSE OR tag_id = ANY(:tags))
        GROUP BY 1,2,3
        ORDER BY bucket
        """
    ),
    "daily": text(
        """
        SELECT
            time_bucket('1 day', bucket_ts) AS bucket,
            lagoon_id,
            tag_id,
            AVG(value_num) AS avg_val
        FROM public.scada_minute
        WHERE lagoon_id = :lagoon_id
          AND bucket_ts BETWEEN :start AND :end
          AND value_num IS NOT NULL
          AND (:use_tags = FALSE OR tag_id = ANY(:tags))
        GROUP BY 1,2,3
        ORDER BY bucket
        """
    ),
    "weekly": text(
        """
        SELECT
            time_bucket('1 week', bucket_ts) AS bucket,
            lagoon_id,
            tag_id,
            AVG(value_num) AS avg_val
        FROM public.scada_minute
        WHERE lagoon_id = :lagoon_id
          AND bucket_ts BETWEEN :start AND :end
          AND value_num IS NOT NULL
          AND (:use_tags = FALSE OR tag_id = ANY(:tags))
        GROUP BY 1,2,3
        ORDER BY bucket
        """
    ),
}


def table_exists(db: Session, qualified_name: str) -> bool:
    row = db.execute(
        text("SELECT to_regclass(:name) AS oid"),
        {"name": qualified_name},
    ).mappings().first()
    return bool(row and row["oid"])


def parse_resolution(resolution: Optional[str]) -> Optional[Resolution]:
    if not resolution:
        return None
    key = resolution.strip().lower()
    if key in RESOLUTION_BY_KEY:
        return cast(Resolution, key)
    return None


def pick_resolution_by_days(days: float) -> ResolutionChoice:
    # Alineado con frontend (<=14 hourly, <=180 daily, resto weekly)
    if days <= 14:
        return RESOLUTION_BY_KEY["hourly"]
    if days <= 180:
        return RESOLUTION_BY_KEY["daily"]
    return RESOLUTION_BY_KEY["weekly"]


def pick_resolution(days: float, requested: Optional[str]) -> ResolutionChoice:
    parsed = parse_resolution(requested)
    if parsed:
        return RESOLUTION_BY_KEY[parsed]
    return pick_resolution_by_days(days)


def _build_params(
    lagoon_id: str,
    start_date: datetime,
    end_date: datetime,
    tags: Optional[List[str]],
) -> dict[str, Any]:
    return {
        "lagoon_id": lagoon_id,
        "start": start_date,
        "end": end_date,
        "use_tags": bool(tags),
        "tags": tags or [],
    }


def fetch_from_view(
    db: Session,
    key: Resolution,
    lagoon_id: str,
    start_date: datetime,
    end_date: datetime,
    tags: Optional[List[str]],
):
    params = _build_params(lagoon_id, start_date, end_date, tags)
    sql = VIEW_QUERY_BY_KEY[key]
    return db.execute(sql, params).mappings().all()


def fetch_fallback_timebucket(
    db: Session,
    key: Resolution,
    lagoon_id: str,
    start_date: datetime,
    end_date: datetime,
    tags: Optional[List[str]],
):
    params = _build_params(lagoon_id, start_date, end_date, tags)
    sql = FALLBACK_QUERY_BY_KEY[key]
    return db.execute(sql, params).mappings().all()


def get_history_rows(
    db: Session,
    lagoon_id: str,
    start_date: datetime,
    end_date: datetime,
    resolution: Optional[str],
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    if end_date < start_date:
        start_date, end_date = end_date, start_date

    days = (end_date - start_date).total_seconds() / 86400.0
    res = pick_resolution(days, resolution) 

    if table_exists(db, res.view):
        rows = fetch_from_view(
            db,
            res.key,
            lagoon_id,
            start_date,
            end_date,
            tags,
        )
        source = "view"
    else:
        rows = fetch_fallback_timebucket(
            db,
            res.key,
            lagoon_id,
            start_date,
            end_date,
            tags,
        )
        source = "table"

    return {
        "rows": rows,
        "resolution": res.key,
        "source": source,
        "requested_resolution": resolution,
    }
