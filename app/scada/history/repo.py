# app/scada/history/repo.py
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional


def get_hourly_history(
    db: Session,
    lagoon_id: str,
    start_date: datetime,
    end_date: datetime,
    tags: Optional[List[str]] = None,
):
    sql = text("""
        SELECT
            date_trunc('hour', bucket_ts) AS bucket_ts,
            tag_id,

            -- Analógicas
            AVG(value_num) AS value_num,

            -- Digitales (si alguna vez estuvo activa en la hora)
            BOOL_OR(value_bool) AS value_bool

        FROM scada_minute
        WHERE lagoon_id = :lagoon_id
          AND bucket_ts BETWEEN :start_date AND :end_date
          AND (
            :tags IS NULL
            OR tag_id = ANY(:tags)
          )
        GROUP BY 1, 2
        ORDER BY 1 ASC
    """)

    params = {
        "lagoon_id": lagoon_id,
        "start_date": start_date,
        "end_date": end_date,
        "tags": tags,
    }

    return db.execute(sql, params).fetchall()
