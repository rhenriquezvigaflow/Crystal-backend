from __future__ import annotations

from collections.abc import Iterable

from fastapi import HTTPException
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.lagoon import Lagoon
from app.models.role import ProductType

ROLE_ADMIN_CRYSTAL = "AdminCrystal"
ROLE_VISUAL_CRYSTAL = "VisualCrystal"
ROLE_ADMIN_SMALL = "AdminSmall"
ROLE_SUPERADMIN = "SuperAdmin"
logger = get_logger("auth.lagoon_scope")

PERMISSION_VIEW = "can_view"
PERMISSION_EDIT = "can_edit"
PERMISSION_CONTROL = "can_control"
VALID_PERMISSIONS = {
    PERMISSION_VIEW,
    PERMISSION_EDIT,
    PERMISSION_CONTROL,
}


def _validate_permission(permission: str) -> str:
    if permission not in VALID_PERMISSIONS:
        raise ValueError(f"Unsupported permission: {permission}")
    return permission


def _normalize_roles(user_roles: Iterable[object] | None) -> set[str]:
    normalized: set[str] = set()

    if user_roles is None:
        return normalized

    for role in user_roles:
        if not isinstance(role, str):
            continue
        cleaned = role.strip()
        if cleaned:
            normalized.add(cleaned)

    return normalized


def resolve_permitted_product_types(
    user_roles: Iterable[object] | None,
) -> set[str]:
    roles = {role.lower() for role in _normalize_roles(user_roles)}

    if ROLE_SUPERADMIN.lower() in roles:
        return {ProductType.CRYSTAL.value, ProductType.SMALL.value}

    permitted: set[str] = set()
    if ROLE_ADMIN_CRYSTAL.lower() in roles or ROLE_VISUAL_CRYSTAL.lower() in roles:
        permitted.add(ProductType.CRYSTAL.value)
    if ROLE_ADMIN_SMALL.lower() in roles:
        permitted.add(ProductType.SMALL.value)

    return permitted


def _assigned_lagoon_ids(db: Session, user_id: str) -> set[str]:
    rows = db.execute(
        text(
            """
            SELECT DISTINCT
                lagoon_id::text AS lagoon_id
            FROM vw_user_lagoons
            WHERE user_id::text = :user_id
              AND can_view = TRUE
            """
        ),
        {"user_id": user_id},
    ).mappings().all()

    return {
        str(row["lagoon_id"])
        for row in rows
        if row.get("lagoon_id") is not None
    }


def _map_lagoon(lagoon: Lagoon) -> dict:
    return {
        "lagoon_id": lagoon.id,
        "lagoon_name": lagoon.name,
        "timezone": lagoon.timezone,
        "ip": lagoon.ip,
        "enable": bool(lagoon.enable),
        "product_type": (
            lagoon.product_type.value
            if isinstance(lagoon.product_type, ProductType)
            else str(lagoon.product_type)
        ),
    }


def _lagoon_product_value(lagoon: Lagoon) -> str:
    if isinstance(lagoon.product_type, ProductType):
        return lagoon.product_type.value
    return str(lagoon.product_type)


def get_lagoon_by_id(db: Session, lagoon_id: str) -> Lagoon | None:
    return (
        db.query(Lagoon)
        .filter(
            Lagoon.id == lagoon_id,
            Lagoon.enable.is_(True),
        )
        .first()
    )


def ensure_lagoon_access(
    db: Session,
    *,
    user_id: str,
    user_email: str,
    user_roles: Iterable[object] | None,
    lagoon_id: str,
    permission: str = PERMISSION_VIEW,
    expected_product_type: ProductType | None = None,
) -> Lagoon:
    lagoon = get_lagoon_by_id(db=db, lagoon_id=lagoon_id)
    roles = sorted(_normalize_roles(user_roles))
    permitted_products = sorted(resolve_permitted_product_types(roles))

    if lagoon is None:
        logger.warning(
            "[LAGOON ACCESS] not_found user_id=%s email=%s lagoon_id=%s roles=%s permitted_products=%s",
            user_id,
            user_email,
            lagoon_id,
            roles,
            permitted_products,
        )
        raise HTTPException(status_code=404, detail="Lagoon not found")

    lagoon_product = _lagoon_product_value(lagoon)
    if expected_product_type and lagoon_product != expected_product_type.value:
        logger.warning(
            "[LAGOON ACCESS] product_mismatch user_id=%s email=%s lagoon_id=%s lagoon_product=%s expected_product=%s roles=%s",
            user_id,
            user_email,
            lagoon_id,
            lagoon_product,
            expected_product_type.value,
            roles,
        )
        raise HTTPException(status_code=404, detail="Lagoon not found")

    if lagoon_product in permitted_products:
        logger.info(
            "[RBAC] user_scope_resolved user_id=%s email=%s lagoon_id=%s lagoon_product=%s permission=%s mode=product_admin roles=%s permitted_products=%s",
            user_id,
            user_email,
            lagoon_id,
            lagoon_product,
            permission,
            roles,
            permitted_products,
        )
        return lagoon

    if permission not in VALID_PERMISSIONS:
        raise ValueError(f"Unsupported permission: {permission}")

    if not user_has_permission(
        db=db,
        user_id=user_id,
        lagoon_id=lagoon_id,
        permission=permission,
    ):
        logger.warning(
            "[LAGOON ACCESS] denied user_id=%s email=%s lagoon_id=%s lagoon_product=%s permission=%s roles=%s permitted_products=%s",
            user_id,
            user_email,
            lagoon_id,
            lagoon_product,
            permission,
            roles,
            permitted_products,
        )
        raise HTTPException(status_code=403, detail="Forbidden")

    logger.info(
        "[RBAC] user_scope_resolved user_id=%s email=%s lagoon_id=%s lagoon_product=%s permission=%s mode=fine_grained roles=%s permitted_products=%s",
        user_id,
        user_email,
        lagoon_id,
        lagoon_product,
        permission,
        roles,
        permitted_products,
    )
    return lagoon


def get_product_lagoons_for_user(
    db: Session,
    user_id: str,
    user_roles: Iterable[object] | None,
    product_type: ProductType,
) -> list[Lagoon]:
    query = (
        db.query(Lagoon)
        .filter(
            Lagoon.product_type == product_type,
            Lagoon.enable.is_(True),
        )
        .order_by(Lagoon.name.asc())
    )

    permitted = resolve_permitted_product_types(user_roles)
    if product_type.value in permitted:
        return query.all()

    assigned_ids = _assigned_lagoon_ids(db=db, user_id=user_id)
    if not assigned_ids:
        return []

    return query.filter(Lagoon.id.in_(assigned_ids)).all()


def get_accessible_lagoons(
    db: Session,
    user_id: str,
    user_roles: Iterable[object] | None = None,
) -> list[dict]:
    assigned_ids = _assigned_lagoon_ids(db=db, user_id=user_id)
    permitted_products = resolve_permitted_product_types(user_roles)

    if not assigned_ids and not permitted_products:
        return []

    filters = []
    if assigned_ids:
        filters.append(Lagoon.id.in_(assigned_ids))

    product_enums = [
        ProductType(product)
        for product in sorted(permitted_products)
    ]
    if product_enums:
        filters.append(Lagoon.product_type.in_(product_enums))

    query = db.query(Lagoon).filter(Lagoon.enable.is_(True)).order_by(Lagoon.name.asc())
    if len(filters) == 1:
        lagoons = query.filter(filters[0]).all()
    else:
        lagoons = query.filter(or_(*filters)).all()

    return [_map_lagoon(lagoon) for lagoon in lagoons]


def user_has_permission(
    db: Session,
    user_id: str,
    lagoon_id: str,
    permission: str,
) -> bool:
    permission_column = _validate_permission(permission)
    exists = db.execute(
        text(
            f"""
            SELECT EXISTS (
                SELECT 1
                FROM vw_user_lagoons vul
                JOIN lagoons l
                  ON l.id::text = vul.lagoon_id::text
                WHERE vul.user_id::text = :user_id
                  AND vul.lagoon_id::text = :lagoon_id
                  AND vul.{permission_column} = TRUE
                  AND l.enable = TRUE
            )
            """
        ),
        {
            "user_id": user_id,
            "lagoon_id": lagoon_id,
        },
    ).scalar()

    return bool(exists)


def user_has_any_permission(
    db: Session,
    user_id: str,
    permission: str,
) -> bool:
    permission_column = _validate_permission(permission)
    exists = db.execute(
        text(
            f"""
            SELECT EXISTS (
                SELECT 1
                FROM vw_user_lagoons vul
                JOIN lagoons l
                  ON l.id::text = vul.lagoon_id::text
                WHERE vul.user_id::text = :user_id
                  AND vul.{permission_column} = TRUE
                  AND l.enable = TRUE
            )
            """
        ),
        {"user_id": user_id},
    ).scalar()

    return bool(exists)
