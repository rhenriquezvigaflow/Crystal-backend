from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class HistoryPoint(BaseModel):
    timestamp: datetime
    value: Optional[float] = None  


class HistorySeries(BaseModel):
    tag_key: str
    name: str
    unit: Optional[str] = None
    decimals: int = 2
    points: List[HistoryPoint]


class HistoryResponse(BaseModel):
    lagoon_id: str
    resolution: str              # "1h" | "1d" | "1w"
    source: str                  # "view" | "table"
    series: List[HistorySeries]
