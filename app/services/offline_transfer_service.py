from __future__ import annotations

import gzip
import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterable
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.lagoon_aliases import normalize_lagoon_id
from app.models.lagoon import Lagoon
from app.models.offline_collector_node import OfflineCollectorNode
from app.models.offline_transfer import (
    OFFLINE_SOURCE,
    OfflineTransfer,
    OfflineTransferPart,
)
from app.schemas.offline_transfer import (
    OfflinePartUploadResponse,
    OfflineTransferManifest,
    OfflineTransferStatusResponse,
)
from app.services.offline_transfer_importer import (
    OfflineTransferImportError,
    import_transfer,
)


ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "UPLOADING": frozenset({"READY", "FAILED", "QUARANTINED"}),
    "READY": frozenset({"IMPORTING", "FAILED", "QUARANTINED"}),
    "IMPORTING": frozenset({"FAILED", "VERIFIED", "QUARANTINED"}),
    "FAILED": frozenset({"READY", "IMPORTING", "QUARANTINED"}),
    "VERIFIED": frozenset(),
    "QUARANTINED": frozenset(),
}
_GLOBAL_IMPORT_LOCK_KEY = 4850184784618498124


@dataclass(frozen=True)
class TransferError(Exception):
    status_code: int
    code: str
    detail: str

    def __str__(self) -> str:
        return self.detail


def transition(transfer: OfflineTransfer, target: str) -> None:
    current = transfer.status
    if target == current:
        return
    if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise TransferError(
            409,
            "invalid_status_transition",
            f"cannot transition transfer from {current} to {target}",
        )
    transfer.status = target
    transfer.updated_at = datetime.now(timezone.utc)


def _storage_root() -> Path:
    return settings.BACKFILL_STORAGE_PATH.expanduser().resolve()


def _safe_child(*parts: str) -> Path:
    root = _storage_root()
    candidate = root.joinpath(*parts).resolve()
    if candidate != root and root not in candidate.parents:
        raise TransferError(500, "invalid_storage_path", "unsafe storage path")
    return candidate


def transfer_parts_dir(transfer_id: UUID) -> Path:
    return _safe_child("Incoming", str(transfer_id), "Parts")


def assembled_file_path(transfer_id: UUID) -> Path:
    return _safe_child("Ready", f"{transfer_id}.csv.gz")


def failed_file_path(transfer_id: UUID) -> Path:
    return _safe_child("Failed", f"{transfer_id}.csv.gz")


def imported_file_path(transfer_id: UUID) -> Path:
    return _safe_child("Imported", f"{transfer_id}.csv.gz")


def _part_file_path(transfer_id: UUID, part_number: int) -> Path:
    return transfer_parts_dir(transfer_id) / f"{part_number:08d}.part"


def _ensure_storage_dirs(transfer_id: UUID) -> None:
    transfer_parts_dir(transfer_id).mkdir(parents=True, exist_ok=True)
    for directory in ("Ready", "Imported", "Failed"):
        _safe_child(directory).mkdir(parents=True, exist_ok=True)
    _safe_child("Failed", "Conflicts", str(transfer_id)).mkdir(
        parents=True,
        exist_ok=True,
    )


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while block := stream.read(settings.BACKFILL_STREAM_BLOCK_BYTES):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def _manifest_dict(manifest: OfflineTransferManifest) -> dict:
    return manifest.model_dump(mode="json")


def _validate_limits(manifest: OfflineTransferManifest) -> None:
    max_part_bytes = settings.BACKFILL_MAX_PART_SIZE_MB * 1024 * 1024
    max_file_bytes = settings.BACKFILL_MAX_FILE_SIZE_MB * 1024 * 1024
    if manifest.row_count > settings.BACKFILL_MAX_ROWS:
        raise TransferError(413, "too_many_rows", "manifest row_count exceeds limit")
    if manifest.uncompressed_size_bytes > max_file_bytes:
        raise TransferError(
            413,
            "uncompressed_file_too_large",
            "manifest uncompressed size exceeds limit",
        )
    if manifest.compressed_size_bytes > max_file_bytes:
        raise TransferError(
            413,
            "compressed_file_too_large",
            "manifest compressed size exceeds limit",
        )
    if manifest.part_size_bytes > max_part_bytes:
        raise TransferError(413, "part_too_large", "manifest part size exceeds limit")
    if manifest.total_parts > settings.BACKFILL_MAX_PARTS:
        raise TransferError(413, "too_many_parts", "manifest total_parts exceeds limit")


def _canonical_manifest(
    node: OfflineCollectorNode,
    manifest: OfflineTransferManifest,
) -> OfflineTransferManifest:
    lagoon_id = normalize_lagoon_id(manifest.lagoon_id)
    if manifest.source != OFFLINE_SOURCE:
        raise TransferError(422, "invalid_source", "source must be collector_offline")
    if node.source_node_id != manifest.source_node_id or node.lagoon_id != lagoon_id:
        raise TransferError(
            403,
            "node_scope_mismatch",
            "offline node is not authorized for this source/lagoon",
        )
    return manifest.model_copy(update={"lagoon_id": lagoon_id})


def _same_manifest(transfer: OfflineTransfer, manifest: OfflineTransferManifest) -> bool:
    return transfer.manifest == _manifest_dict(manifest)


def _identity_candidates(
    db: Session,
    manifest: OfflineTransferManifest,
) -> list[OfflineTransfer]:
    return list(
        db.scalars(
            select(OfflineTransfer).where(
                (OfflineTransfer.transfer_id == manifest.transfer_id)
                | (OfflineTransfer.chunk_id == manifest.chunk_id)
                | (
                    (OfflineTransfer.source_node_id == manifest.source_node_id)
                    & (OfflineTransfer.sequence_number == manifest.sequence)
                )
            )
        ).all()
    )


def _existing_identity_match(
    candidates: list[OfflineTransfer],
    manifest: OfflineTransferManifest,
) -> OfflineTransfer | None:
    if not candidates:
        return None
    existing = candidates[0]
    if (
        all(candidate.transfer_id == existing.transfer_id for candidate in candidates)
        and _same_manifest(existing, manifest)
    ):
        return existing
    raise TransferError(
        409,
        "transfer_identity_conflict",
        "transfer, chunk or node sequence already identifies different metadata",
    )


def create_transfer(
    db: Session,
    node: OfflineCollectorNode,
    manifest: OfflineTransferManifest,
) -> tuple[OfflineTransfer, bool]:
    manifest = _canonical_manifest(node, manifest)
    _validate_limits(manifest)

    lagoon = db.scalar(
        select(Lagoon).where(Lagoon.id == manifest.lagoon_id, Lagoon.enable.is_(True))
    )
    if lagoon is None:
        raise TransferError(404, "lagoon_not_found", "lagoon not found or disabled")

    existing = _existing_identity_match(_identity_candidates(db, manifest), manifest)
    if existing is not None:
        return existing, False

    transfer = OfflineTransfer(
        transfer_id=manifest.transfer_id,
        chunk_id=manifest.chunk_id,
        schema_version=manifest.schema_version,
        data_kind=manifest.data_kind,
        source=OFFLINE_SOURCE,
        source_node_id=manifest.source_node_id,
        lagoon_id=manifest.lagoon_id,
        sequence_number=manifest.sequence,
        file_name=manifest.file_name,
        format=manifest.format,
        compression=manifest.compression,
        row_count=manifest.row_count,
        uncompressed_size_bytes=manifest.uncompressed_size_bytes,
        compressed_size_bytes=manifest.compressed_size_bytes,
        part_size_bytes=manifest.part_size_bytes,
        total_parts=manifest.total_parts,
        from_timestamp=manifest.from_timestamp,
        to_timestamp=manifest.to_timestamp,
        sha256=manifest.sha256,
        manifest=_manifest_dict(manifest),
        status="UPLOADING",
    )
    _ensure_storage_dirs(transfer.transfer_id)
    node.last_seen_at = datetime.now(timezone.utc)
    db.add(transfer)
    try:
        db.commit()
    except IntegrityError:
        # A simultaneous retry can pass the initial read before the first
        # request commits. Resolve the unique-key race as the same idempotent
        # result instead of leaking an internal error.
        db.rollback()
        existing = _existing_identity_match(
            _identity_candidates(db, manifest),
            manifest,
        )
        if existing is None:
            raise
        return existing, False
    db.refresh(transfer)
    return transfer, True


def get_transfer_for_node(
    db: Session,
    node: OfflineCollectorNode,
    transfer_id: UUID,
    *,
    for_update: bool = False,
) -> OfflineTransfer:
    statement = select(OfflineTransfer).where(
        OfflineTransfer.transfer_id == transfer_id,
        OfflineTransfer.source_node_id == node.source_node_id,
    )
    if for_update:
        statement = statement.with_for_update()
    transfer = db.scalar(statement)
    if transfer is None:
        raise TransferError(404, "transfer_not_found", "transfer not found")
    return transfer


def _confirmed_parts(db: Session, transfer_id: UUID) -> list[int]:
    return list(
        db.scalars(
            select(OfflineTransferPart.part_number)
            .where(OfflineTransferPart.transfer_id == transfer_id)
            .order_by(OfflineTransferPart.part_number)
        ).all()
    )


def status_response(db: Session, transfer: OfflineTransfer) -> OfflineTransferStatusResponse:
    confirmed = _confirmed_parts(db, transfer.transfer_id)
    confirmed_set = set(confirmed)
    missing = [
        number
        for number in range(1, transfer.total_parts + 1)
        if number not in confirmed_set
    ]
    return OfflineTransferStatusResponse(
        transfer_id=transfer.transfer_id,
        chunk_id=transfer.chunk_id,
        data_kind=transfer.data_kind,
        status=transfer.status,
        received_parts=confirmed,
        confirmed_parts=confirmed,
        missing_parts=missing,
        expected_rows=transfer.row_count,
        row_count=transfer.row_count,
        staged_rows=transfer.staged_rows,
        inserted_rows=transfer.inserted_rows,
        duplicate_rows=transfer.duplicate_rows,
        retry_count=transfer.retry_count,
        last_error_code=transfer.last_error_code,
        last_error=transfer.last_error,
        verified_at=transfer.verified_at,
    )


def expected_part_spec(transfer: OfflineTransfer, part_number: int) -> tuple[int, int]:
    if part_number < 1 or part_number > transfer.total_parts:
        raise TransferError(404, "part_not_found", "part number is outside manifest")
    offset = (part_number - 1) * transfer.part_size_bytes
    size = min(
        transfer.part_size_bytes,
        transfer.compressed_size_bytes - offset,
    )
    return offset, size


def _quarantine_file(transfer_id: UUID, path: Path, suffix: str) -> None:
    if not path.exists():
        return
    target = _safe_child(
        "Failed",
        "Conflicts",
        str(transfer_id),
        f"{path.name}.{suffix}.{uuid4().hex}",
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(path, target)


def _mark_quarantined(
    db: Session,
    transfer: OfflineTransfer,
    *,
    code: str,
    detail: str,
) -> None:
    if transfer.status != "QUARANTINED":
        transition(transfer, "QUARANTINED")
    transfer.last_error_code = code
    transfer.last_error = detail[:4000]
    transfer.quarantined_at = datetime.now(timezone.utc)
    transfer.lease_owner = None
    transfer.lease_expires_at = None
    db.commit()


async def receive_part(
    db: Session,
    node: OfflineCollectorNode,
    transfer_id: UUID,
    part_number: int,
    *,
    byte_offset: int | None,
    content_length: int,
    part_sha256: str,
    body: AsyncIterable[bytes],
) -> OfflinePartUploadResponse:
    transfer = get_transfer_for_node(db, node, transfer_id, for_update=True)
    expected_offset, expected_size = expected_part_spec(transfer, part_number)
    if content_length > settings.BACKFILL_MAX_PART_SIZE_MB * 1024 * 1024:
        raise TransferError(413, "part_too_large", "part exceeds configured limit")
    byte_offset = expected_offset if byte_offset is None else byte_offset
    if byte_offset != expected_offset or content_length != expected_size:
        raise TransferError(
            409,
            "part_metadata_mismatch",
            "part offset or size does not match manifest",
        )

    existing = db.get(OfflineTransferPart, (transfer_id, part_number))
    if existing is not None:
        path = Path(existing.file_path)
        actual_sha256, actual_size = (
            _sha256_file(path) if path.is_file() else (None, None)
        )
        file_present = path.is_file()
        file_matches = (
            actual_size == content_length and actual_sha256 == part_sha256
            if file_present
            else transfer.status == "VERIFIED"
            and transfer.files_cleaned_at is not None
        )
        metadata_matches = (
            existing.byte_offset == byte_offset
            and existing.size_bytes == content_length
            and existing.sha256 == part_sha256
            and file_matches
        )
        if not metadata_matches:
            if transfer.status == "VERIFIED":
                raise TransferError(
                    409,
                    "verified_part_conflict",
                    "part metadata differs from a verified transfer",
                )
            _mark_quarantined(
                db,
                transfer,
                code="stored_part_conflict",
                detail="confirmed part metadata or file is inconsistent",
            )
            raise TransferError(
                409,
                "stored_part_conflict",
                "confirmed part is inconsistent; transfer quarantined",
            )
        return OfflinePartUploadResponse(
            transfer_id=transfer_id,
            part_number=part_number,
            status="already_received",
            confirmed_parts=_confirmed_parts(db, transfer_id),
        )

    if transfer.status != "UPLOADING":
        raise TransferError(
            409,
            "transfer_not_uploading",
            f"parts are not accepted while transfer is {transfer.status}",
        )

    _ensure_storage_dirs(transfer_id)
    final_path = _part_file_path(transfer_id, part_number)
    if final_path.exists():
        actual_sha256, actual_size = _sha256_file(final_path)
        if actual_sha256 == part_sha256 and actual_size == content_length:
            db.add(
                OfflineTransferPart(
                    transfer_id=transfer_id,
                    part_number=part_number,
                    byte_offset=byte_offset,
                    size_bytes=content_length,
                    sha256=part_sha256,
                    file_path=str(final_path),
                )
            )
            db.commit()
            return OfflinePartUploadResponse(
                transfer_id=transfer_id,
                part_number=part_number,
                status="already_received",
                confirmed_parts=_confirmed_parts(db, transfer_id),
            )
        _quarantine_file(transfer_id, final_path, "orphan-conflict")
        _mark_quarantined(
            db,
            transfer,
            code="orphan_part_conflict",
            detail="orphan part file does not match retry metadata",
        )
        raise TransferError(
            409,
            "orphan_part_conflict",
            "orphan part is inconsistent; transfer quarantined",
        )

    temporary_path = final_path.with_name(f".{final_path.name}.{uuid4().hex}.uploading")
    digest = hashlib.sha256()
    bytes_written = 0
    try:
        with temporary_path.open("xb") as stream:
            async for block in body:
                if not block:
                    continue
                bytes_written += len(block)
                if bytes_written > expected_size:
                    raise TransferError(413, "part_too_large", "part body exceeds manifest")
                digest.update(block)
                stream.write(block)
            stream.flush()
            os.fsync(stream.fileno())
        if bytes_written != expected_size:
            raise TransferError(400, "part_size_mismatch", "part body is incomplete")
        if digest.hexdigest() != part_sha256:
            raise TransferError(422, "part_checksum_mismatch", "part SHA-256 mismatch")
        os.replace(temporary_path, final_path)
        db.add(
            OfflineTransferPart(
                transfer_id=transfer_id,
                part_number=part_number,
                byte_offset=byte_offset,
                size_bytes=bytes_written,
                sha256=part_sha256,
                file_path=str(final_path),
            )
        )
        transfer.updated_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        if temporary_path.exists():
            temporary_path.unlink(missing_ok=True)
        db.rollback()
        raise

    return OfflinePartUploadResponse(
        transfer_id=transfer_id,
        part_number=part_number,
        status="received",
        confirmed_parts=_confirmed_parts(db, transfer_id),
    )


def _validate_assembled_gzip(path: Path, expected_uncompressed_size: int) -> None:
    uncompressed_size = 0
    try:
        with gzip.open(path, "rb") as stream:
            while block := stream.read(settings.BACKFILL_STREAM_BLOCK_BYTES):
                uncompressed_size += len(block)
                if uncompressed_size > expected_uncompressed_size:
                    raise TransferError(
                        422,
                        "uncompressed_size_mismatch",
                        "gzip expands beyond manifest size",
                    )
    except (gzip.BadGzipFile, EOFError, OSError) as exc:
        raise TransferError(422, "invalid_gzip", "assembled file is not valid gzip") from exc
    if uncompressed_size != expected_uncompressed_size:
        raise TransferError(
            422,
            "uncompressed_size_mismatch",
            "gzip uncompressed size does not match manifest",
        )


def _validate_complete_file(path: Path, transfer: OfflineTransfer) -> None:
    actual_sha256, actual_size = _sha256_file(path)
    if actual_size != transfer.compressed_size_bytes:
        raise TransferError(
            422,
            "compressed_size_mismatch",
            "assembled size does not match manifest",
        )
    if actual_sha256 != transfer.sha256:
        raise TransferError(
            422,
            "file_checksum_mismatch",
            "assembled SHA-256 does not match manifest",
        )
    _validate_assembled_gzip(path, transfer.uncompressed_size_bytes)


def _transfer_file(transfer: OfflineTransfer) -> Path:
    if not transfer.assembled_path:
        raise TransferError(
            409,
            "assembled_file_missing",
            "transfer has no assembled file",
        )
    path = Path(transfer.assembled_path).resolve()
    root = _storage_root()
    if root not in path.parents:
        raise TransferError(500, "invalid_storage_path", "unsafe assembled path")
    if not path.is_file():
        raise TransferError(
            409,
            "assembled_file_missing",
            "assembled file does not exist",
        )
    return path


def _parts_for_transfer(
    db: Session,
    transfer: OfflineTransfer,
) -> list[OfflineTransferPart]:
    parts = list(
        db.scalars(
            select(OfflineTransferPart)
            .where(OfflineTransferPart.transfer_id == transfer.transfer_id)
            .order_by(OfflineTransferPart.part_number)
        ).all()
    )
    received_numbers = {part.part_number for part in parts}
    missing = [
        number
        for number in range(1, transfer.total_parts + 1)
        if number not in received_numbers
    ]
    if missing:
        raise TransferError(
            409,
            "parts_missing",
            f"missing parts: {','.join(str(number) for number in missing)}",
        )
    return parts


def _assemble_to_ready(
    db: Session,
    node: OfflineCollectorNode,
    transfer: OfflineTransfer,
) -> OfflineTransfer:
    parts = _parts_for_transfer(db, transfer)
    _ensure_storage_dirs(transfer.transfer_id)
    final_path = assembled_file_path(transfer.transfer_id)
    temporary_path = final_path.with_name(
        f".{final_path.name}.{uuid4().hex}.assembling"
    )
    digest = hashlib.sha256()
    total_size = 0
    try:
        with temporary_path.open("xb") as destination:
            for part in parts:
                expected_offset, expected_size = expected_part_spec(
                    transfer,
                    part.part_number,
                )
                if part.byte_offset != expected_offset or part.size_bytes != expected_size:
                    raise TransferError(
                        409,
                        "stored_part_metadata_mismatch",
                        "stored part metadata is inconsistent",
                    )
                part_path = Path(part.file_path)
                if not part_path.is_file():
                    raise TransferError(
                        409,
                        "part_file_missing",
                        "stored part file is missing",
                    )
                part_digest = hashlib.sha256()
                part_size = 0
                with part_path.open("rb") as source:
                    while block := source.read(settings.BACKFILL_STREAM_BLOCK_BYTES):
                        destination.write(block)
                        digest.update(block)
                        part_digest.update(block)
                        part_size += len(block)
                        total_size += len(block)
                if part_size != part.size_bytes or part_digest.hexdigest() != part.sha256:
                    raise TransferError(
                        409,
                        "stored_part_checksum_mismatch",
                        "stored part file differs from confirmed metadata",
                    )
            destination.flush()
            os.fsync(destination.fileno())

        if total_size != transfer.compressed_size_bytes:
            raise TransferError(
                422,
                "compressed_size_mismatch",
                "assembled size does not match manifest",
            )
        _validate_complete_file(temporary_path, transfer)
        os.replace(temporary_path, final_path)
    except TransferError:
        if temporary_path.exists():
            failed_path = failed_file_path(transfer.transfer_id)
            failed_path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temporary_path, failed_path)
        raise
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    transfer.assembled_path = str(final_path)
    transition(transfer, "READY")
    transfer.received_at = datetime.now(timezone.utc)
    transfer.last_error_code = None
    transfer.last_error = None
    node.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(transfer)
    return transfer


def _restore_failed_to_ready(
    db: Session,
    transfer: OfflineTransfer,
) -> OfflineTransfer:
    current_path = _transfer_file(transfer)
    _validate_complete_file(current_path, transfer)
    ready_path = assembled_file_path(transfer.transfer_id)
    ready_path.parent.mkdir(parents=True, exist_ok=True)
    if current_path != ready_path:
        os.replace(current_path, ready_path)
    transfer.assembled_path = str(ready_path)
    transition(transfer, "READY")
    transfer.last_error_code = None
    transfer.last_error = None
    db.commit()
    db.refresh(transfer)
    return transfer


def _advisory_key(transfer_id: UUID) -> int:
    value = int.from_bytes(
        hashlib.sha256(transfer_id.bytes).digest()[:8],
        byteorder="big",
        signed=False,
    )
    return value if value < 2**63 else value - 2**64


def _acquire_import_locks(db: Session, transfer_id: UUID) -> None:
    lock_sql = text("SELECT pg_try_advisory_xact_lock(:lock_key)")
    if not bool(db.scalar(lock_sql, {"lock_key": _GLOBAL_IMPORT_LOCK_KEY})):
        raise TransferError(
            409,
            "import_in_progress",
            "another offline import is currently running",
        )
    if not bool(db.scalar(lock_sql, {"lock_key": _advisory_key(transfer_id)})):
        raise TransferError(
            409,
            "transfer_import_in_progress",
            "this transfer is currently being imported",
        )


def _persist_failed(
    db: Session,
    node: OfflineCollectorNode,
    transfer_id: UUID,
    *,
    code: str,
    detail: str,
) -> None:
    db.rollback()
    transfer = get_transfer_for_node(db, node, transfer_id, for_update=True)
    if transfer.status in {"VERIFIED", "QUARANTINED"}:
        db.rollback()
        return

    existing_path: Path | None = None
    if transfer.assembled_path:
        candidate = Path(transfer.assembled_path).resolve()
        if _storage_root() in candidate.parents and candidate.is_file():
            existing_path = candidate
    preserved_path = failed_file_path(transfer_id)
    if existing_path is None:
        for candidate in (
            preserved_path,
            imported_file_path(transfer_id),
            assembled_file_path(transfer_id),
        ):
            if candidate.is_file():
                existing_path = candidate
                break
    if existing_path is not None and existing_path != preserved_path:
        preserved_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(existing_path, preserved_path)
        existing_path = preserved_path
    if existing_path is not None:
        transfer.assembled_path = str(existing_path)

    transition(transfer, "FAILED")
    transfer.retry_count += 1
    transfer.next_retry_at = None
    transfer.lease_owner = None
    transfer.lease_expires_at = None
    transfer.last_error_code = code[:64]
    transfer.last_error = detail[:4000]
    node.last_seen_at = datetime.now(timezone.utc)
    db.commit()


def _begin_import(
    db: Session,
    node: OfflineCollectorNode,
    transfer_id: UUID,
) -> OfflineTransfer:
    _acquire_import_locks(db, transfer_id)
    transfer = get_transfer_for_node(db, node, transfer_id, for_update=True)
    if transfer.status == "VERIFIED":
        db.rollback()
        return transfer
    if transfer.status not in {"READY", "FAILED", "IMPORTING"}:
        raise TransferError(
            409,
            "transfer_not_ready",
            f"transfer cannot be imported while {transfer.status}",
        )
    if transfer.status != "IMPORTING":
        transition(transfer, "IMPORTING")
    transfer.import_started_at = datetime.now(timezone.utc)
    transfer.last_error_code = None
    transfer.last_error = None
    transfer.next_retry_at = None
    node.last_seen_at = datetime.now(timezone.utc)
    # Persist IMPORTING so a process crash is recoverable through POST /complete.
    db.commit()
    db.refresh(transfer)
    return transfer


def complete_transfer(
    db: Session,
    node: OfflineCollectorNode,
    transfer_id: UUID,
) -> OfflineTransfer:
    transfer = get_transfer_for_node(db, node, transfer_id, for_update=True)
    if transfer.status == "VERIFIED":
        return transfer
    if transfer.status == "QUARANTINED":
        raise TransferError(409, "transfer_quarantined", "transfer is quarantined")

    try:
        if transfer.status == "UPLOADING":
            transfer = _assemble_to_ready(db, node, transfer)
        elif transfer.status == "FAILED":
            transfer = _restore_failed_to_ready(db, transfer)
        elif transfer.status in {"READY", "IMPORTING"}:
            _validate_complete_file(_transfer_file(transfer), transfer)
    except TransferError as exc:
        if exc.code == "parts_missing":
            raise
        _persist_failed(
            db,
            node,
            transfer_id,
            code=exc.code,
            detail=exc.detail,
        )
        raise

    try:
        transfer = _begin_import(db, node, transfer_id)
        if transfer.status == "VERIFIED":
            return transfer
    except TransferError:
        db.rollback()
        raise

    try:
        _acquire_import_locks(db, transfer_id)
    except TransferError:
        db.rollback()
        raise

    try:
        transfer = get_transfer_for_node(db, node, transfer_id, for_update=True)
        if transfer.status == "VERIFIED":
            db.rollback()
            return transfer
        if transfer.status != "IMPORTING":
            raise TransferError(
                409,
                "transfer_not_importing",
                f"transfer cannot finish import while {transfer.status}",
            )
        _validate_complete_file(_transfer_file(transfer), transfer)
        counts = import_transfer(db, transfer)
        if counts.staged_rows != transfer.row_count:
            raise OfflineTransferImportError(
                "row_count_not_reconciled",
                "staged row count differs from manifest",
                permanent=False,
            )
        if counts.inserted_rows + counts.duplicate_rows != transfer.row_count:
            raise OfflineTransferImportError(
                "import_counts_mismatch",
                "inserted plus duplicate rows differs from manifest",
                permanent=False,
            )

        transfer.staged_rows = counts.staged_rows
        transfer.inserted_rows = counts.inserted_rows
        transfer.duplicate_rows = counts.duplicate_rows
        current_path = _transfer_file(transfer)
        imported_path = imported_file_path(transfer_id)
        imported_path.parent.mkdir(parents=True, exist_ok=True)
        if current_path != imported_path:
            os.replace(current_path, imported_path)
        transfer.assembled_path = str(imported_path)
        transition(transfer, "VERIFIED")
        transfer.verified_at = datetime.now(timezone.utc)
        transfer.last_error_code = None
        transfer.last_error = None
        transfer.lease_owner = None
        transfer.lease_expires_at = None
        transfer.next_retry_at = None
        node.last_seen_at = datetime.now(timezone.utc)
        # COPY, merge, counters and VERIFIED commit atomically.
        db.commit()
        return transfer
    except OfflineTransferImportError as exc:
        _persist_failed(
            db,
            node,
            transfer_id,
            code=exc.code,
            detail=exc.detail,
        )
        raise TransferError(
            422 if exc.permanent else 503,
            exc.code,
            exc.detail,
        ) from exc
    except TransferError as exc:
        _persist_failed(
            db,
            node,
            transfer_id,
            code=exc.code,
            detail=exc.detail,
        )
        raise
    except (OperationalError, DBAPIError) as exc:
        detail = str(exc).splitlines()[0] or type(exc).__name__
        _persist_failed(
            db,
            node,
            transfer_id,
            code="database_error",
            detail=detail,
        )
        raise TransferError(
            503,
            "database_error",
            "database import failed; retry complete",
        ) from exc
    except Exception as exc:
        detail = str(exc).splitlines()[0] or type(exc).__name__
        _persist_failed(
            db,
            node,
            transfer_id,
            code="import_error",
            detail=detail,
        )
        raise TransferError(
            500,
            "import_error",
            "offline import failed; retry complete",
        ) from exc
