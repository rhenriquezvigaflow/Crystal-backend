from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

VALID_SEVERITIES = {"info", "warning", "critical"}
Severity = Literal["info", "warning", "critical"]
ThresholdSource = Literal["configured", "candidate"]


class ThresholdViewRowOut(BaseModel):
    tag_id: str
    tag_name: str | None = None
    source: ThresholdSource
    min_value: float | None = None
    max_value: float | None = None
    severity: Severity = "warning"
    enabled: bool = True


class ThresholdViewResponse(BaseModel):
    lagoon_id: str
    rows: list[ThresholdViewRowOut]


class ThresholdConfigItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tag_id: str
    min_value: float | None = None
    max_value: float | None = None
    severity: Severity = "warning"
    enabled: bool = True

    @field_validator("tag_id")
    @classmethod
    def validate_tag_id(cls, value: str) -> str:
        tag_id = value.strip().upper()
        if not tag_id:
            raise ValueError("tag_id is required")
        if not (tag_id.startswith("PT") or tag_id.startswith("FIT")):
            raise ValueError(f"tag_id '{tag_id}' is not PT/FIT")
        return tag_id

    @field_validator("severity", mode="before")
    @classmethod
    def validate_severity(cls, value: str) -> str:
        normalized = str(value).strip().lower()
        if normalized not in VALID_SEVERITIES:
            allowed = ", ".join(sorted(VALID_SEVERITIES))
            raise ValueError(f"severity must be one of: {allowed}")
        return normalized

    @model_validator(mode="after")
    def validate_limits(self) -> "ThresholdConfigItem":
        if self.min_value is None and self.max_value is None:
            raise ValueError(
                f"tag_id '{self.tag_id}' requires min_value or max_value"
            )

        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value >= self.max_value
        ):
            raise ValueError(
                f"tag_id '{self.tag_id}' invalid limits: "
                f"min_value ({self.min_value}) must be < max_value ({self.max_value})"
            )

        return self


class ThresholdConfigRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ThresholdConfigItem] = Field(
        default_factory=list,
        min_length=1,
    )


class ThresholdUpsertResponse(BaseModel):
    ok: bool = True
    lagoon_id: str
    created: list[str]
    updated: list[str]
