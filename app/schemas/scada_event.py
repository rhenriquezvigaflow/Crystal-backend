from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PumpEvent(BaseModel):
    lagoon_id: str
    tag_id: str
    tag_label: Optional[str] = None
    start_local: datetime


class LastPumpEventsResponse(BaseModel):
    lagoon_id: str
    events: list[PumpEvent]
