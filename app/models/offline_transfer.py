from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


OFFLINE_SOURCE = "collector_offline"


class OfflineTransfer(Base):
    __tablename__ = "offline_transfer"
    __table_args__ = (
        UniqueConstraint("chunk_id", name="uq_offline_transfer_chunk_id"),
        UniqueConstraint(
            "source_node_id",
            "sequence_number",
            name="uq_offline_transfer_node_sequence",
        ),
        CheckConstraint(
            "source = 'collector_offline'",
            name="ck_offline_transfer_source",
        ),
        CheckConstraint(
            "data_kind = 'minute'",
            name="ck_offline_transfer_data_kind",
        ),
        CheckConstraint("format = 'csv'", name="ck_offline_transfer_format"),
        CheckConstraint(
            "compression = 'gzip'",
            name="ck_offline_transfer_compression",
        ),
        CheckConstraint(
            "status IN ('UPLOADING', 'READY', 'IMPORTING', "
            "'VERIFIED', 'FAILED', 'QUARANTINED')",
            name="ck_offline_transfer_status",
        ),
        CheckConstraint(
            "row_count > 0 AND uncompressed_size_bytes > 0 "
            "AND compressed_size_bytes > 0 AND part_size_bytes > 0 "
            "AND total_parts > 0",
            name="ck_offline_transfer_positive_sizes",
        ),
        CheckConstraint(
            "from_timestamp <= to_timestamp",
            name="ck_offline_transfer_timestamp_range",
        ),
        Index(
            "ix_offline_transfer_status",
            "status",
            "created_at",
        ),
        Index(
            "ix_offline_transfer_node_created",
            "source_node_id",
            "created_at",
        ),
    )

    transfer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True
    )
    chunk_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    data_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=OFFLINE_SOURCE,
        server_default=text("'collector_offline'"),
    )
    source_node_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("offline_collector_node.source_node_id", ondelete="RESTRICT"),
        nullable=False,
    )
    lagoon_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("lagoons.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sequence_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    format: Mapped[str] = mapped_column(String(8), nullable=False)
    compression: Mapped[str] = mapped_column(String(8), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    uncompressed_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    compressed_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    part_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    total_parts: Mapped[int] = mapped_column(Integer, nullable=False)
    from_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    to_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="UPLOADING", server_default="UPLOADING"
    )
    assembled_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    staged_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inserted_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duplicate_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    import_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    quarantined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    files_cleaned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class OfflineTransferPart(Base):
    __tablename__ = "offline_transfer_part"
    __table_args__ = (
        UniqueConstraint(
            "transfer_id",
            "byte_offset",
            name="uq_offline_transfer_part_offset",
        ),
        CheckConstraint("part_number > 0", name="ck_offline_transfer_part_number"),
        CheckConstraint(
            "byte_offset >= 0 AND size_bytes > 0",
            name="ck_offline_transfer_part_size",
        ),
    )

    transfer_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("offline_transfer.transfer_id", ondelete="CASCADE"),
        primary_key=True,
    )
    part_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    byte_offset: Mapped[int] = mapped_column(BigInteger, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
