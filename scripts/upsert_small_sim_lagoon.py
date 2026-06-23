from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert

from app.db.session import SessionLocal
from app.models.lagoon import Lagoon
from app.models.role import ProductType


def main() -> None:
    payload = {
        "id": "small_sim",
        "name": "Small Simulator",
        "plc_type": "siemens",
        "timezone": "America/Santiago",
        "ip": "192.168.100.10",
        "enable": True,
        "product_type": ProductType.SMALL,
    }

    with SessionLocal() as db:
        stmt = insert(Lagoon).values(**payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "name": stmt.excluded.name,
                "plc_type": stmt.excluded.plc_type,
                "timezone": stmt.excluded.timezone,
                "ip": stmt.excluded.ip,
                "enable": stmt.excluded.enable,
                "product_type": stmt.excluded.product_type,
            },
        )
        db.execute(stmt)
        db.commit()


if __name__ == "__main__":
    main()
