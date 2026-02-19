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