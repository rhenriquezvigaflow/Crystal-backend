from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any

class CollectorPayload(BaseModel):
    lagoon_id: str
    source: str = Field(..., examples=["rockwell", "siemens"])
    timestamp: datetime
    tags: dict[str, Any]
