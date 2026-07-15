from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal


LAGOON_ID = "laguna_baia_kristal"


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
                    scada_layout,
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
                    :scada_layout,
                    :product_type,
                    TRUE
                )
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    plc_type = EXCLUDED.plc_type,
                    country_id = EXCLUDED.country_id,
                    timezone = EXCLUDED.timezone,
                    ip = EXCLUDED.ip,
                    scada_layout = EXCLUDED.scada_layout,
                    product_type = EXCLUDED.product_type,
                    enable = EXCLUDED.enable
                """
            ),
            {
                "id": LAGOON_ID,
                "name": "Baia Kristal",
                "plc_type": "Rockwell",
                "country_code": "CO",
                "timezone": "America/Bogota",
                "ip": "192.168.14.10",
                "scada_layout": "layout2",
                "product_type": "crystal",
            },
        )
        db.commit()


if __name__ == "__main__":
    main()
