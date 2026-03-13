from __future__ import annotations

from app.db.session import SessionLocal
from app.models.role import ProductType, Role

SEED_ROLES: list[tuple[str, ProductType]] = [
    ("AdminCrystal", ProductType.CRYSTAL),
    ("VisualCrystal", ProductType.CRYSTAL),
    ("AdminSmall", ProductType.SMALL),
    ("VisualSmall", ProductType.SMALL),
]


def seed_roles() -> int:
    db = SessionLocal()
    inserted = 0

    try:
        existing = {
            (row.name, row.product_type)
            for row in db.query(Role).all()
        }

        for name, product_type in SEED_ROLES:
            key = (name, product_type)
            if key in existing:
                continue
            db.add(
                Role(
                    name=name,
                    product_type=product_type,
                )
            )
            inserted += 1

        db.commit()
        return inserted
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    created = seed_roles()
    print(f"seed_roles: inserted={created}")
