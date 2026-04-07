from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Dict, List, Literal, Optional

from app.auth.services.lagoon_service import PERMISSION_VIEW, ensure_lagoon_access
from app.core.logging import get_logger
from app.db.session import get_db
from app.scada.history.repo import get_history_rows
from app.security.rbac import ALL_READ_ROLES, extract_user_roles, require_roles


router = APIRouter(
    prefix="/scada/history",
    tags=["SCADA History"],
)
logger = get_logger("api.scada.history")


def _extract_user_id(user: dict) -> str:
    user_id = user.get("sub")
    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return user_id

@router.get("/{resolution}")
def get_history(
    resolution: Literal["hourly", "daily", "weekly"],
    lagoon_id: str = Query(...),
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    tags: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db),
    user: dict = Depends(require_roles(ALL_READ_ROLES)),
):
    user_id = _extract_user_id(user)
    email = str(user.get("email", "-"))
    roles = extract_user_roles(user)
    ensure_lagoon_access(
        db=db,
        user_id=user_id,
        user_email=email,
        user_roles=roles,
        lagoon_id=lagoon_id,
        permission=PERMISSION_VIEW,
    )

    data = get_history_rows(
        db=db,
        lagoon_id=lagoon_id,
        start_date=start_date,
        end_date=end_date,
        resolution=resolution,
        tags=tags,
    )

    series_map: Dict[str, list] = {}

    for r in data["rows"]:
        tag = r["tag_id"]
        series_map.setdefault(tag, []).append({
            "timestamp": r["bucket"],
            "value": float(r["avg_val"]) if r["avg_val"] is not None else None,
        })

    response = {
        "lagoon_id": lagoon_id,
        "resolution": data["resolution"],
        "source": data["source"],
        "series": [
            {"tag": tag, "points": points}
            for tag, points in series_map.items()
        ],
    }
    logger.info(
        "[API] endpoint_response_summary endpoint=/scada/history/%s user_id=%s lagoon_id=%s roles=%s tags_requested=%s series_count=%s source=%s",
        resolution,
        user_id,
        lagoon_id,
        roles,
        len(tags or []),
        len(response["series"]),
        response["source"],
    )
    return response
