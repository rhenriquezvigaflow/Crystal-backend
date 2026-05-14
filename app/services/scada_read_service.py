from sqlalchemy.orm import Session

from app.core.lagoon_aliases import normalize_lagoon_id
from app.repositories.scada_read_repository import ScadaReadRepository
from app.scada.value_codec import from_storage_fields
from app.state.store import RealtimeStateStore


def build_tags(rows):
    """
    Construye el payload de tags respetando la semántica:

    prioridad:
    1) state       -> estados discretos (0,1,2,3)
    2) value_bool  -> booleanos reales
    3) value_num   -> analógicos
    """
    tags = {}

    for r in rows:
        tags[r.tag_id] = from_storage_fields(
            state=r.state,
            value_bool=r.value_bool,
            value_num=r.value_num,
        )

    return tags


def _build_scada_response(lagoon_id: str, ts, rows):
    canonical_lagoon_id = normalize_lagoon_id(lagoon_id)
    return {
        "lagoon_id": canonical_lagoon_id,
        "ts": ts,
        "tags": build_tags(rows),
    }


def _build_realtime_response(
    lagoon_id: str,
    state_store: RealtimeStateStore,
):
    canonical_lagoon_id = normalize_lagoon_id(lagoon_id)
    snapshot = state_store.snapshot(canonical_lagoon_id)
    ts = snapshot.get("ts")
    tags = snapshot.get("tags")

    if ts is None or not isinstance(tags, dict) or not tags:
        return None

    return {
        "lagoon_id": canonical_lagoon_id,
        "ts": ts,
        "tags": tags,
    }


def get_last_minute(lagoon_id: str, db: Session):
    canonical_lagoon_id = normalize_lagoon_id(lagoon_id)
    bucket, rows = ScadaReadRepository.get_last_minute(db, canonical_lagoon_id)
    if not rows:
        return None

    return _build_scada_response(canonical_lagoon_id, bucket, rows)


def get_current(
    lagoon_id: str,
    db: Session,
    state_store: RealtimeStateStore | None = None,
):
    canonical_lagoon_id = normalize_lagoon_id(lagoon_id)
    if state_store is not None:
        realtime = _build_realtime_response(canonical_lagoon_id, state_store)
        if realtime is not None:
            return realtime

    rows = ScadaReadRepository.get_current(db, canonical_lagoon_id)
    if not rows:
        return None

    ts = max(r.bucket for r in rows)

    return _build_scada_response(canonical_lagoon_id, ts, rows)
