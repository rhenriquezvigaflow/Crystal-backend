from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict,Any

class ScadaSnapshot(BaseModel):
    lagoon_id: str 
    ts: datetime 
    tags: Dict[str, Any]

class ScadaCurrent(BaseModel):
    lagoon_id: str
    ts: datetime
    tags: Dict[str, Any]


class ScadaKpis(BaseModel):
    lagoon_id: str
    ts: datetime | None = None
    plc_status: str | None = None
    local_time: str | None = None
    timezone: str | None = None
    tags_count: int = 0
    pump_events_count: int = 0
    pump_last_on: Dict[str, str] = Field(default_factory=dict)
