from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.scada import ScadaSnapshot, ScadaCurrent
from app.services.scada_read_service import (
    get_last_minute,
    get_current,
)

router = APIRouter(prefix="/scada", tags=["SCADA"])


@router.get("/{lagoon_id}/last-minute", response_model=ScadaSnapshot)
def last_minute(lagoon_id: str, db: Session = Depends(get_db)):
    data = get_last_minute(lagoon_id, db)
    if not data:
        raise HTTPException(404, "No data")
    return data


@router.get("/{lagoon_id}/current", response_model=ScadaCurrent)
def current(lagoon_id: str, db: Session = Depends(get_db)):
    data = get_current(lagoon_id, db)
    if not data:
        raise HTTPException(404, "No data")
    return data
