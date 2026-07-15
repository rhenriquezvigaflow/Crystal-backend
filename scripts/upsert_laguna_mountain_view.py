from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal


LAGOON_ID = "laguna_mountain_view"


def main() -> None:
    with SessionLocal() as db:
        db.execute(
            text(
                """
                INSERT INTO lagoons (
                    id,
                    name,
                    plc_type,
                    country_id,
                    timezone,
                    ip,
                    product_type,
                    enable
                )
                VALUES (
                    :id,
                    :name,
                    :plc_type,
                    (SELECT id FROM countries WHERE code = :country_code),
                    :timezone,
                    CAST(:ip AS inet),
                    :product_type,
                    TRUE
                )
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    plc_type = EXCLUDED.plc_type,
                    country_id = EXCLUDED.country_id,
                    timezone = EXCLUDED.timezone,
                    ip = EXCLUDED.ip,
                    product_type = EXCLUDED.product_type,
                    enable = EXCLUDED.enable
                """
            ),
            {
                "id": LAGOON_ID,
                "name": "Mountain View",
                "plc_type": "Rockwell",
                "country_code": "EG",
                "timezone": "Africa/Cairo",
                "ip": "192.168.26.10",
                "product_type": "crystal",
            },
        )
        db.commit()


if __name__ == "__main__":
    main()
