from sqlalchemy.orm import Session
from app.repositories.scada_read_repository import ScadaReadRepository
from app.scada.value_codec import from_storage_fields


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
    return {
        "lagoon_id": lagoon_id,
        "ts": ts,
        "tags": build_tags(rows),
    }


def get_last_minute(lagoon_id: str, db: Session):
    bucket, rows = ScadaReadRepository.get_last_minute(db, lagoon_id)
    if not rows:
        return None

    return _build_scada_response(lagoon_id, bucket, rows)


def get_current(lagoon_id: str, db: Session):
    rows = ScadaReadRepository.get_current(db, lagoon_id)
    if not rows:
        return None

    ts = max(r.bucket for r in rows)

    return _build_scada_response(lagoon_id, ts, rows)
