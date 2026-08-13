from __future__ import annotations

from datetime import datetime
from pathlib import PurePath
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.offline_transfer import OFFLINE_SOURCE


SHA256_PATTERN = r"^[0-9a-f]{64}$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OfflineTransferManifest(StrictModel):
    schema_version: Literal[1]
    transfer_id: UUID
    chunk_id: UUID
    sequence: int = Field(ge=1)
    source: Literal[OFFLINE_SOURCE]
    source_node_id: str = Field(min_length=1, max_length=128)
    lagoon_id: str = Field(min_length=1, max_length=64)
    data_kind: Literal["minute"] = "minute"
    format: Literal["csv"]
    compression: Literal["gzip"]
    file_name: str = Field(min_length=1, max_length=255)
    row_count: int = Field(ge=1)
    uncompressed_size_bytes: int = Field(ge=1)
    compressed_size_bytes: int = Field(ge=1)
    part_size_bytes: int = Field(ge=64 * 1024)
    total_parts: int = Field(ge=1)
    from_timestamp: datetime
    to_timestamp: datetime
    sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator("file_name")
    @classmethod
    def validate_file_name(cls, value: str) -> str:
        if PurePath(value).name != value or "/" in value or "\\" in value:
            raise ValueError("file_name must be a base name")
        if not value.endswith(".csv.gz"):
            raise ValueError("file_name must end with .csv.gz")
        return value

    @model_validator(mode="after")
    def validate_manifest_consistency(self) -> "OfflineTransferManifest":
        if self.from_timestamp.tzinfo is None or self.to_timestamp.tzinfo is None:
            raise ValueError("manifest timestamps must be timezone-aware")
        if self.from_timestamp > self.to_timestamp:
            raise ValueError("from_timestamp must not exceed to_timestamp")
        expected_parts = (
            self.compressed_size_bytes + self.part_size_bytes - 1
        ) // self.part_size_bytes
        if self.total_parts != expected_parts:
            raise ValueError("total_parts does not match compressed size")
        return self


class OfflineTransferStatusResponse(StrictModel):
    transfer_id: UUID
    chunk_id: UUID
    data_kind: Literal["minute"]
    status: Literal[
        "UPLOADING",
        "READY",
        "IMPORTING",
        "VERIFIED",
        "FAILED",
        "QUARANTINED",
    ]
    received_parts: list[int]
    confirmed_parts: list[int]
    missing_parts: list[int]
    expected_rows: int
    row_count: int
    staged_rows: int | None = None
    inserted_rows: int | None = None
    duplicate_rows: int | None = None
    retry_count: int = 0
    last_error_code: str | None = None
    last_error: str | None = None
    verified_at: datetime | None = None


class OfflinePartUploadResponse(StrictModel):
    transfer_id: UUID
    part_number: int
    status: Literal["received", "already_received"]
    confirmed_parts: list[int]
