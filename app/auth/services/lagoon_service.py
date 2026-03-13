from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

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


def get_accessible_lagoons(db: Session, user_id: str) -> list[dict]:
    rows = db.execute(
        text(
            """
            SELECT DISTINCT
                lagoon_id::text AS lagoon_id,
                lagoon_name,
                scada_layout,
                timezone,
                ip
            FROM vw_user_lagoons
            WHERE user_id::text = :user_id
              AND can_view = TRUE
            ORDER BY lagoon_name ASC
            """
        ),
        {"user_id": user_id},
    ).mappings().all()

    return [dict(row) for row in rows]


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
                FROM vw_user_lagoons
                WHERE user_id::text = :user_id
                  AND lagoon_id::text = :lagoon_id
                  AND {permission_column} = TRUE
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
                FROM vw_user_lagoons
                WHERE user_id::text = :user_id
                  AND {permission_column} = TRUE
            )
            """
        ),
        {"user_id": user_id},
    ).scalar()

    return bool(exists)
