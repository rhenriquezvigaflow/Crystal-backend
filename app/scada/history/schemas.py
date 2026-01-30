from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class HistoryPoint(BaseModel):
    timestamp: datetime
    value: float


class HistorySeries(BaseModel):
    tag_key: str
    name: str
    unit: Optional[str] = None
    decimals: int = 2
    points: List[HistoryPoint]


class HistoryHourlyResponse(BaseModel):
    lagoon_id: str
    resolution: str = "1h"
    series: List[HistorySeries]