from sqlalchemy.orm import Session
from app.repositories.scada_read_repository import ScadaReadRepository


def build_tags(rows):
    tags = {}
    for r in rows:
        if r.value_bool is not None:
            tags[r.tag_id] = r.value_bool
        else:
            tags[r.tag_id] = r.value_num
    return tags


def get_last_minute(lagoon_id: str, db: Session):
    bucket_ts, rows = ScadaReadRepository.get_last_minute(db, lagoon_id)
    if not rows:
        return None

    return {
        "lagoon_id": lagoon_id,
        "ts": bucket_ts,
        "tags": build_tags(rows),
    }


def get_current(lagoon_id: str, db: Session):
    rows = ScadaReadRepository.get_current(db, lagoon_id)
    if not rows:
        return None

    ts = max(r.bucket_ts for r in rows)

    return {
        "lagoon_id": lagoon_id,
        "ts": ts,
        "tags": build_tags(rows),
    }
