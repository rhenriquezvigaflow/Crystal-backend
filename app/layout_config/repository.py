from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.lagoon_layout_mapping import LagoonLayoutMapping
from app.models.layout import Layout


class LayoutConfigRepository:
    _COLLECTOR_TAGS_SQL = text(
        """
        SELECT tag_id
        FROM collector_tag_registry
        WHERE lagoon_id = :lagoon_id
        ORDER BY tag_id
        """
    )

    def get_layout(
        self,
        *,
        db: Session,
        layout_id: str,
    ) -> Layout | None:
        return (
            db.query(Layout)
            .filter(Layout.id == layout_id)
            .first()
        )

    def get_mapping_for_layout(
        self,
        *,
        db: Session,
        lagoon_id: str,
        layout_id: str,
    ) -> tuple[dict[str, Any], datetime | None]:
        row = (
            db.query(
                LagoonLayoutMapping.mapping_json,
                LagoonLayoutMapping.updated_at,
            )
            .filter(
                LagoonLayoutMapping.lagoon_id == lagoon_id,
                LagoonLayoutMapping.layout_id == layout_id,
            )
            .first()
        )
        if row is None:
            return {}, None

        mapping_json, updated_at = row
        if not isinstance(mapping_json, dict):
            return {}, updated_at

        return dict(mapping_json), updated_at

    def get_collector_tags(
        self,
        *,
        db: Session,
        lagoon_id: str,
    ) -> list[str]:
        rows = db.execute(
            self._COLLECTOR_TAGS_SQL,
            {"lagoon_id": lagoon_id},
        ).scalars().all()

        return [
            str(tag_id).strip()
            for tag_id in rows
            if isinstance(tag_id, str) and tag_id.strip()
        ]

    def upsert_mapping(
        self,
        *,
        db: Session,
        lagoon_id: str,
        layout_id: str,
        mapping_json: dict[str, Any],
    ) -> None:
        stmt = insert(LagoonLayoutMapping).values(
            lagoon_id=lagoon_id,
            layout_id=layout_id,
            mapping_json=mapping_json,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                LagoonLayoutMapping.lagoon_id,
                LagoonLayoutMapping.layout_id,
            ],
            set_={
                "mapping_json": stmt.excluded.mapping_json,
                "updated_at": func.now(),
            },
        )
        db.execute(stmt)
