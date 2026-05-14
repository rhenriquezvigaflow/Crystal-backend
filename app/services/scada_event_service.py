from __future__ import annotations

from app.core.lagoon_aliases import normalize_lagoon_id
from app.repositories.scada_event_repository import ScadaEventRepository
from sqlalchemy.orm import Session


def get_recent_events(
    *,
    db: Session,
    lagoon_id: str,
    limit: int,
) -> list[dict]:
    canonical_lagoon_id = normalize_lagoon_id(lagoon_id)
    return ScadaEventRepository.get_recent_events_by_lagoon(
        db=db,
        lagoon_id=canonical_lagoon_id,
        limit=limit,
    )


def get_recent_pump_events(
    *,
    db: Session,
    lagoon_id: str,
    limit: int,
) -> list[dict]:
    canonical_lagoon_id = normalize_lagoon_id(lagoon_id)
    return ScadaEventRepository.get_recent_events_by_lagoon(
        db=db,
        lagoon_id=canonical_lagoon_id,
        limit=limit,
    )


def get_last_3_pump_events(
    *,
    db: Session,
    lagoon_id: str,
) -> list[dict]:
    canonical_lagoon_id = normalize_lagoon_id(lagoon_id)
    return ScadaEventRepository.get_last_3_events_by_lagoon(
        db=db,
        lagoon_id=canonical_lagoon_id,
    )
