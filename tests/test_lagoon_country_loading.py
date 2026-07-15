from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.auth.services.lagoon_service import (
    get_lagoon_permissions,
    get_product_lagoons_for_user,
)
from app.models.country import Country
from app.models.lagoon import Lagoon
from app.models.role import ProductType
from app.modules.shared.product_router import _map_lagoon_access


def test_product_lagoons_load_country_in_one_query():
    engine = create_engine("sqlite://")
    Country.__table__.create(engine)
    Lagoon.__table__.create(engine)

    with Session(engine) as db:
        db.add_all(
            [
                Country(id=7, code="CO", name="Colombia"),
                Lagoon(
                    id="laguna_baia_kristal",
                    name="Baia Kristal",
                    country_id=7,
                    enable=True,
                    product_type=ProductType.CRYSTAL,
                ),
            ]
        )
        db.commit()
        db.expire_all()

        statements: list[str] = []

        @event.listens_for(engine, "before_cursor_execute")
        def collect_statement(*_args):
            statements.append(_args[2])

        lagoons = get_product_lagoons_for_user(
            db=db,
            user_id="1",
            user_roles=["AdminCrystal"],
            product_type=ProductType.CRYSTAL,
        )

        assert len(statements) == 1
        assert lagoons[0].country is not None
        assert lagoons[0].country.name == "Colombia"
        assert len(statements) == 1


def test_product_lagoon_payload_includes_country_fields():
    lagoon = SimpleNamespace(
        id="laguna_baia_kristal",
        name="Baia Kristal",
        plc_type="Rockwell",
        country_id=7,
        country=SimpleNamespace(name="Colombia"),
        timezone="America/Bogota",
        ip="192.168.14.10",
        enable=True,
        product_type=ProductType.CRYSTAL,
    )

    payload = _map_lagoon_access(
        lagoon=lagoon,
        user_id="1",
        user_roles=["AdminCrystal"],
        write_roles=["AdminCrystal"],
        lagoon_permissions={},
    )

    assert payload["country_id"] == 7
    assert payload["country_name"] == "Colombia"


def test_lagoon_permissions_are_loaded_in_one_batch_query():
    class _Result:
        def mappings(self):
            return self

        def all(self):
            return [
                {
                    "lagoon_id": "laguna_baia_kristal",
                    "can_edit": False,
                    "can_control": True,
                }
            ]

    class _Session:
        def __init__(self):
            self.calls = 0

        def execute(self, *_args, **_kwargs):
            self.calls += 1
            return _Result()

    db = _Session()
    permissions = get_lagoon_permissions(
        db=db,
        user_id="1",
        lagoon_ids=["laguna_baia_kristal", "laguna_baia_kristal"],
    )

    assert db.calls == 1
    assert permissions == {
        "laguna_baia_kristal": {
            "can_edit": False,
            "can_control": True,
        }
    }
