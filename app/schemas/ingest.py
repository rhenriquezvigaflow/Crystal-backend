from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any

from app.models.role import ProductType

class CollectorPayload(BaseModel):
    lagoon_id: str
    product_type: ProductType | None = None
    source: str = Field(..., examples=["rockwell", "siemens"])
    timestamp: datetime
    tags: dict[str, Any]
