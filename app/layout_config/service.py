from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.layout_config.repository import LayoutConfigRepository
from app.layout_config.schemas import (
    LayoutConfigResponse,
    LayoutDefinition,
    LayoutResponse,
    LagoonLayoutMappingResponse,
)
from app.models.lagoon import Lagoon
from app.scada.layout_resolver import normalize_scada_layout

DEFAULT_LAYOUT_CONFIG_CACHE_TTL_SEC = 300
logger = get_logger("layout.config.service")


def _load_layout_config_cache_ttl_sec() -> int:
    raw = os.getenv(
        "SCADA_LAYOUT_CACHE_TTL_SEC",
        os.getenv(
            "LAYOUT_CONFIG_CACHE_TTL_SEC",
            str(DEFAULT_LAYOUT_CONFIG_CACHE_TTL_SEC),
        ),
    )
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        parsed = DEFAULT_LAYOUT_CONFIG_CACHE_TTL_SEC
    return max(0, parsed)


class LagoonLayoutConfigRepositoryProtocol(Protocol):
    def get_layout(
        self,
        *,
        db: Session,
        layout_id: str,
    ): ...

    def get_mapping_for_layout(
        self,
        *,
        db: Session,
        lagoon_id: str,
        layout_id: str,
    ) -> tuple[dict[str, Any], Any]: ...

    def upsert_mapping(
        self,
        *,
        db: Session,
        lagoon_id: str,
        layout_id: str,
        mapping_json: dict[str, Any],
    ) -> None: ...

    def get_collector_tags(
        self,
        *,
        db: Session,
        lagoon_id: str,
    ) -> list[str]: ...


@dataclass(slots=True)
class _LagoonLayoutConfigCacheEntry:
    expires_at: float
    value: LayoutConfigResponse


@dataclass(slots=True)
class _LayoutCacheEntry:
    expires_at: float
    value: LayoutResponse


class LagoonLayoutConfigService:
    def __init__(
        self,
        *,
        repository: LagoonLayoutConfigRepositoryProtocol | None = None,
        ttl_sec: int | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._repository = repository or LayoutConfigRepository()
        self._ttl_sec = _load_layout_config_cache_ttl_sec() if ttl_sec is None else max(0, int(ttl_sec))
        self._clock = clock or time.monotonic
        self._lock = threading.RLock()
        self._mapping_cache: dict[str, _LagoonLayoutConfigCacheEntry] = {}
        self._layout_cache: dict[str, _LayoutCacheEntry] = {}

    def _mapping_cache_key(self, lagoon_id: str, layout_id: str) -> str:
        return f"{lagoon_id}:{layout_id}"

    def _mapping_cache_get(self, lagoon_id: str, layout_id: str) -> LayoutConfigResponse | None:
        cache_key = self._mapping_cache_key(lagoon_id, layout_id)
        with self._lock:
            entry = self._mapping_cache.get(cache_key)
            if entry is None:
                return None
            if self._clock() >= entry.expires_at:
                self._mapping_cache.pop(cache_key, None)
                return None
            return entry.value

    def _mapping_cache_set(self, lagoon_id: str, layout_id: str, value: LayoutConfigResponse) -> None:
        if self._ttl_sec <= 0:
            return
        cache_key = self._mapping_cache_key(lagoon_id, layout_id)
        with self._lock:
            self._mapping_cache[cache_key] = _LagoonLayoutConfigCacheEntry(
                expires_at=self._clock() + self._ttl_sec,
                value=value,
            )

    def _layout_cache_get(self, layout_id: str) -> LayoutResponse | None:
        with self._lock:
            entry = self._layout_cache.get(layout_id)
            if entry is None:
                return None
            if self._clock() >= entry.expires_at:
                self._layout_cache.pop(layout_id, None)
                return None
            return entry.value

    def _layout_cache_set(self, layout_id: str, value: LayoutResponse) -> None:
        if self._ttl_sec <= 0:
            return
        with self._lock:
            self._layout_cache[layout_id] = _LayoutCacheEntry(
                expires_at=self._clock() + self._ttl_sec,
                value=value,
            )

    def _normalize_mapping_json(self, mapping_json: dict[str, Any]) -> dict[str, dict[str, Any]]:
        normalized: dict[str, dict[str, Any]] = {}

        for element_id, raw_value in mapping_json.items():
            if not isinstance(element_id, str):
                continue

            clean_element_id = element_id.strip()
            if not clean_element_id:
                continue

            if isinstance(raw_value, str):
                entry: dict[str, Any] = {"tag": raw_value.strip()}
            elif isinstance(raw_value, dict):
                entry = {
                    str(key).strip(): value
                    for key, value in raw_value.items()
                    if isinstance(key, str)
                }
            else:
                continue

            for key in ("tag", "label", "svg_target"):
                if isinstance(entry.get(key), str):
                    entry[key] = entry[key].strip() or None

            normalized[clean_element_id] = entry

        return normalized

    def _layout_element_ids(self, layout: LayoutResponse) -> set[str]:
        return {element.id for element in layout.json_definition.elements}

    def _mapping_warnings(self, *, layout: LayoutResponse, mapping_json: dict[str, dict[str, Any]]) -> list[str]:
        valid_ids = self._layout_element_ids(layout)
        return [
            f"Mapping references unknown layout element '{element_id}'"
            for element_id in sorted(mapping_json.keys())
            if element_id not in valid_ids
        ]

    def invalidate_cache(self, lagoon_id: str) -> None:
        with self._lock:
            stale_keys = [key for key in self._mapping_cache if key.startswith(f"{lagoon_id}:")]
            for cache_key in stale_keys:
                self._mapping_cache.pop(cache_key, None)

    def clear_cache(self) -> None:
        with self._lock:
            self._mapping_cache.clear()
            self._layout_cache.clear()

    def get_layout(self, *, db: Session, layout_id: str) -> LayoutResponse:
        normalized_layout_id = normalize_scada_layout(layout_id)
        cached = self._layout_cache_get(normalized_layout_id)
        if cached is not None:
            return cached

        layout_row = self._repository.get_layout(db=db, layout_id=normalized_layout_id)
        if layout_row is None:
            raise HTTPException(status_code=404, detail="Layout not found")

        definition = LayoutDefinition.model_validate(layout_row.json_definition or {})
        response = LayoutResponse(
            id=layout_row.id,
            name=layout_row.name,
            json_definition=definition,
            updated_at=layout_row.updated_at,
        )
        self._layout_cache_set(normalized_layout_id, response)
        return response

    def get_lagoon_mapping(self, *, db: Session, lagoon: Lagoon) -> LagoonLayoutMappingResponse:
        config = self.get_layout_config(db=db, lagoon=lagoon)
        return config.mapping

    def get_layout_config(self, *, db: Session, lagoon: Lagoon) -> LayoutConfigResponse:
        layout_id = normalize_scada_layout(lagoon.scada_layout)
        cached = self._mapping_cache_get(lagoon.id, layout_id)
        collector_tags = self._repository.get_collector_tags(
            db=db,
            lagoon_id=lagoon.id,
        )
        if cached is not None:
            if cached.mapping.collector_tags == collector_tags:
                return cached

            refreshed = LayoutConfigResponse(
                lagoon_id=cached.lagoon_id,
                layout=cached.layout,
                mapping=LagoonLayoutMappingResponse(
                    lagoon_id=cached.mapping.lagoon_id,
                    layout_id=cached.mapping.layout_id,
                    mapping_json=cached.mapping.mapping_json,
                    collector_tags=collector_tags,
                    warnings=cached.mapping.warnings,
                    updated_at=cached.mapping.updated_at,
                ),
            )
            self._mapping_cache_set(lagoon.id, layout_id, refreshed)
            return refreshed

        layout = self.get_layout(db=db, layout_id=layout_id)
        mapping_json, updated_at = self._repository.get_mapping_for_layout(
            db=db,
            lagoon_id=lagoon.id,
            layout_id=layout_id,
        )
        normalized_mapping_json = self._normalize_mapping_json(mapping_json)
        warnings = self._mapping_warnings(layout=layout, mapping_json=normalized_mapping_json)
        if warnings:
            logger.warning(
                "[LAYOUT CONFIG] lagoon_id=%s layout_id=%s warnings=%s",
                lagoon.id,
                layout_id,
                warnings,
            )

        response = LayoutConfigResponse(
            lagoon_id=lagoon.id,
            layout=layout,
            mapping=LagoonLayoutMappingResponse(
                lagoon_id=lagoon.id,
                layout_id=layout_id,
                mapping_json=normalized_mapping_json,
                collector_tags=collector_tags,
                warnings=warnings,
                updated_at=updated_at,
            ),
        )
        self._mapping_cache_set(lagoon.id, layout_id, response)
        return response

    def update_layout_config(
        self,
        *,
        db: Session,
        lagoon: Lagoon,
        layout_id: str,
        mapping_json: dict[str, Any],
    ) -> LayoutConfigResponse:
        normalized_layout_id = normalize_scada_layout(layout_id)
        layout = self.get_layout(db=db, layout_id=normalized_layout_id)
        normalized_mapping_json = self._normalize_mapping_json(mapping_json)
        warnings = self._mapping_warnings(layout=layout, mapping_json=normalized_mapping_json)
        if warnings:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Mapping references unknown layout elements",
                    "warnings": warnings,
                },
            )

        self._repository.upsert_mapping(
            db=db,
            lagoon_id=lagoon.id,
            layout_id=normalized_layout_id,
            mapping_json=normalized_mapping_json,
        )
        lagoon.scada_layout = normalized_layout_id
        db.flush()

        self.invalidate_cache(lagoon.id)
        return self.get_layout_config(db=db, lagoon=lagoon)


layout_config_service = LagoonLayoutConfigService()
