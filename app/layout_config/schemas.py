from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LayoutElementDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    type: str
    position: dict[str, str] | None = None
    svg_target: str | None = None
    default_label: str | None = None
    fallback_tag: str | None = None
    unit: str | None = None
    icon_type: str | None = None
    panel: str | None = None

    @field_validator("id", "type", mode="before")
    @classmethod
    def normalize_required_strings(cls, value: object) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("layout element requires a non-empty string")
        return text


class LayoutDefinition(BaseModel):
    model_config = ConfigDict(extra="allow")

    plant: str | None = None
    version: str | None = None
    description: str | None = None
    svg_component: str | None = None
    aspect_ratio: str | None = None
    elements: list[LayoutElementDefinition] = Field(default_factory=list)

    @field_validator("elements", mode="before")
    @classmethod
    def normalize_elements(cls, value: object) -> list[dict[str, Any]]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("elements must be an array")
        return [item for item in value if isinstance(item, dict)]


class LayoutResponse(BaseModel):
    id: str
    name: str
    json_definition: LayoutDefinition
    updated_at: datetime | None = None


class LayoutMappingEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    tag: str | None = None
    label: str | None = None
    svg_target: str | None = None

    @field_validator("tag", "label", "svg_target", mode="before")
    @classmethod
    def normalize_strings(cls, value: object) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None


class LagoonLayoutMappingResponse(BaseModel):
    lagoon_id: str
    layout_id: str
    mapping_json: dict[str, LayoutMappingEntry] = Field(default_factory=dict)
    collector_tags: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None


class LayoutConfigResponse(BaseModel):
    lagoon_id: str
    layout: LayoutResponse
    mapping: LagoonLayoutMappingResponse


class LayoutConfigUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    layout_id: str
    mapping_json: dict[str, LayoutMappingEntry] = Field(default_factory=dict)

    @field_validator("layout_id", mode="before")
    @classmethod
    def normalize_layout_id(cls, value: object) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("layout_id is required")
        return text

    @field_validator("mapping_json", mode="before")
    @classmethod
    def normalize_mapping_json(cls, value: object) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("mapping_json must be an object")
        return value

    @classmethod
    def model_validate(cls, obj: Any, *args: Any, **kwargs: Any):
        if isinstance(obj, dict) and "mapping_json" not in obj and "tag_map" in obj:
            legacy_mapping = obj.get("tag_map")
            if isinstance(legacy_mapping, dict):
                obj = {
                    **obj,
                    "mapping_json": {
                        key: {"tag": value}
                        for key, value in legacy_mapping.items()
                    },
                }
        return super().model_validate(obj, *args, **kwargs)
