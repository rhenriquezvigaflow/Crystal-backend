from __future__ import annotations

import asyncio
import csv
import gzip
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.config import settings
from app.models.offline_transfer import OfflineTransfer
from app.schemas.offline_transfer import OfflineTransferManifest
from app.services import offline_transfer_importer as importer
from app.services import offline_transfer_service as service


def _manifest(**overrides) -> dict:
    payload = {
        "schema_version": 1,
        "transfer_id": uuid4(),
        "chunk_id": uuid4(),
        "sequence": 1,
        "source": "collector_offline",
        "source_node_id": "edge-small-sim-01",
        "lagoon_id": "small_sim",
        "data_kind": "minute",
        "format": "csv",
        "compression": "gzip",
        "file_name": "chunk-000001.csv.gz",
        "row_count": 2,
        "uncompressed_size_bytes": 1000,
        "compressed_size_bytes": 100000,
        "part_size_bytes": 65536,
        "total_parts": 2,
        "from_timestamp": "2026-07-27T10:30:00Z",
        "to_timestamp": "2026-07-27T10:31:00Z",
        "sha256": "a" * 64,
    }
    payload.update(overrides)
    return payload


def _transfer(*, data_kind: str = "minute", row_count: int = 2) -> OfflineTransfer:
    return OfflineTransfer(
        transfer_id=uuid4(),
        chunk_id=uuid4(),
        schema_version=1,
        data_kind=data_kind,
        source="collector_offline",
        source_node_id="edge-small-sim-01",
        lagoon_id="small_sim",
        sequence_number=1,
        file_name="chunk.csv.gz",
        format="csv",
        compression="gzip",
        row_count=row_count,
        uncompressed_size_bytes=1,
        compressed_size_bytes=1,
        part_size_bytes=65536,
        total_parts=1,
        from_timestamp=datetime(2026, 7, 27, 10, 30, tzinfo=timezone.utc),
        to_timestamp=datetime(2026, 7, 27, 10, 31, tzinfo=timezone.utc),
        sha256="a" * 64,
        manifest={},
        status="UPLOADING",
    )


def _write_csv_gzip(path: Path, header: tuple[str, ...], rows: list[list[str]]) -> None:
    with gzip.open(path, "wt", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def test_manifest_enforces_constant_source_part_math_and_safe_name():
    parsed = OfflineTransferManifest.model_validate(_manifest())
    assert parsed.source == "collector_offline"

    with pytest.raises(ValidationError, match="collector_offline"):
        OfflineTransferManifest.model_validate(_manifest(source="small_sim"))
    with pytest.raises(ValidationError, match="total_parts"):
        OfflineTransferManifest.model_validate(_manifest(total_parts=3))
    with pytest.raises(ValidationError, match="base name"):
        OfflineTransferManifest.model_validate(_manifest(file_name="../chunk.csv.gz"))
    with pytest.raises(ValidationError, match="minute"):
        OfflineTransferManifest.model_validate(_manifest(data_kind="event"))


def test_minute_csv_gzip_is_validated_streaming_with_exact_header_and_source(tmp_path):
    path = tmp_path / "minute.csv.gz"
    rows = [
        [
            "small_sim",
            "PT203_R",
            "2026-07-27T10:30:00Z",
            "",
            "2.45",
            "",
            "collector_offline",
        ],
        [
            "small_sim",
            "PT203_R",
            "2026-07-27T10:31:00Z",
            "",
            "2.50",
            "",
            "collector_offline",
        ],
    ]
    _write_csv_gzip(path, importer.MINUTE_CSV_HEADER, rows)
    summary = importer.validate_csv_gzip(path, _transfer())
    assert summary.row_count == 2

    rows[1][-1] = "Collector_offline"
    _write_csv_gzip(path, importer.MINUTE_CSV_HEADER, rows)
    with pytest.raises(importer.OfflineTransferImportError) as error:
        importer.validate_csv_gzip(path, _transfer())
    assert error.value.code == "invalid_source"


def test_offline_import_persists_the_connection_source_label(monkeypatch):
    class FakeCursor:
        rowcount = 1

        def __init__(self):
            self.queries = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, query, *_params):
            self.queries.append(query)

        def fetchone(self):
            return (0,)

    cursor = FakeCursor()
    monkeypatch.setattr(importer, "_raw_cursor", lambda _db: cursor)
    monkeypatch.setattr(importer, "_set_import_timeouts", lambda _cursor: None)
    monkeypatch.setattr(importer, "_copy_gzip", lambda *_args: None)
    monkeypatch.setattr(
        importer, "_validate_common_stage", lambda *_args: 1
    )

    result = importer._import_minutes(SimpleNamespace(), Path("unused.csv.gz"), _transfer(row_count=1))

    assert result.inserted_rows == 1
    assert any("Collector_offline" in query for query in cursor.queries)


def test_minute_csv_rejects_unaligned_non_utc_and_non_deterministic_rows(tmp_path):
    path = tmp_path / "minute.csv.gz"
    rows = [
        ["small_sim", "TAG_B", "2026-07-27T10:30:00Z", "1", "", "", "collector_offline"],
        ["small_sim", "TAG_A", "2026-07-27T10:30:00Z", "2", "", "", "collector_offline"],
    ]
    transfer = _transfer()
    transfer.to_timestamp = transfer.from_timestamp
    _write_csv_gzip(path, importer.MINUTE_CSV_HEADER, rows)
    with pytest.raises(importer.OfflineTransferImportError) as error:
        importer.validate_csv_gzip(path, transfer)
    assert error.value.code == "non_deterministic_order"

    rows[0][2] = "2026-07-27T10:30:30Z"
    rows[1][2] = "2026-07-27T10:31:00Z"
    _write_csv_gzip(path, importer.MINUTE_CSV_HEADER, rows)
    with pytest.raises(importer.OfflineTransferImportError) as error:
        importer.validate_csv_gzip(path, _transfer())
    assert error.value.code == "unaligned_bucket"


def test_event_csv_is_a_separate_kind_and_preserves_source(tmp_path):
    path = tmp_path / "event.csv.gz"
    event_id = str(uuid4())
    rows = [
        [
            event_id,
            "small_sim",
            "P001_ST",
            "Pump 1",
            "STATE_CHANGE",
            "0",
            "1",
            "2026-07-27T10:30:00Z",
            "2026-07-27T10:31:00Z",
            "60",
            "collector_offline",
        ]
    ]
    transfer = _transfer(data_kind="event", row_count=1)
    transfer.to_timestamp = transfer.from_timestamp
    _write_csv_gzip(path, importer.EVENT_CSV_HEADER, rows)
    summary = importer.validate_csv_gzip(path, transfer)
    assert summary.row_count == 1


def test_import_timeout_is_applied_to_copy_transaction():
    class Cursor:
        def __init__(self):
            self.calls = []

        def execute(self, sql, params):
            self.calls.append((sql, params))

    cursor = Cursor()
    importer._set_import_timeouts(cursor)
    assert cursor.calls == [
        (
            "SELECT set_config('statement_timeout', %s, true)",
            (str(settings.BACKFILL_IMPORT_STATEMENT_TIMEOUT_MS),),
        )
    ]


def test_state_machine_rejects_invalid_or_terminal_transitions():
    transfer = _transfer()
    service.transition(transfer, "READY")
    service.transition(transfer, "IMPORTING")
    service.transition(transfer, "VERIFIED")
    with pytest.raises(service.TransferError, match="cannot transition"):
        service.transition(transfer, "IMPORTING")


def test_raw_part_write_is_atomic_and_lost_response_retry_is_idempotent(
    tmp_path,
    monkeypatch,
):
    payload = b"compressed bytes"
    digest = hashlib.sha256(payload).hexdigest()
    transfer = _transfer(row_count=1)
    transfer.compressed_size_bytes = len(payload)
    transfer.part_size_bytes = len(payload)
    transfer.total_parts = 1
    transfer.files_cleaned_at = None
    node = SimpleNamespace(source_node_id=transfer.source_node_id)

    class FakeDb:
        def __init__(self, existing=None):
            self.existing = existing
            self.added = None

        def get(self, _model, _key):
            return self.existing

        def add(self, value):
            self.added = value

        def commit(self):
            return None

        def rollback(self):
            return None

    async def body():
        yield payload[:4]
        yield payload[4:]

    monkeypatch.setattr(settings, "BACKFILL_STORAGE_PATH", tmp_path)
    monkeypatch.setattr(service, "get_transfer_for_node", lambda *_args, **_kwargs: transfer)
    monkeypatch.setattr(service, "_confirmed_parts", lambda *_args: [1])

    first_db = FakeDb()
    first = asyncio.run(
        service.receive_part(
            first_db,
            node,
            transfer.transfer_id,
            1,
            byte_offset=0,
            content_length=len(payload),
            part_sha256=digest,
            body=body(),
        )
    )
    assert first.status == "received"
    stored_part = first_db.added
    assert Path(stored_part.file_path).read_bytes() == payload
    assert not list(Path(stored_part.file_path).parent.glob("*.uploading"))

    async def body_must_not_be_read():
        raise AssertionError("already_received must not consume the request body")
        yield b""

    second = asyncio.run(
        service.receive_part(
            FakeDb(existing=stored_part),
            node,
            transfer.transfer_id,
            1,
            byte_offset=0,
            content_length=len(payload),
            part_sha256=digest,
            body=body_must_not_be_read(),
        )
    )
    assert second.status == "already_received"

    stored_path = Path(stored_part.file_path)
    stored_path.write_bytes(b"x" * len(payload))
    transfer.status = "VERIFIED"
    with pytest.raises(service.TransferError) as conflict:
        asyncio.run(
            service.receive_part(
                FakeDb(existing=stored_part),
                node,
                transfer.transfer_id,
                1,
                byte_offset=0,
                content_length=len(payload),
                part_sha256=digest,
                body=body_must_not_be_read(),
            )
        )
    assert conflict.value.code == "verified_part_conflict"

    stored_path.unlink()
    transfer.files_cleaned_at = datetime.now(timezone.utc)
    after_cleanup = asyncio.run(
        service.receive_part(
            FakeDb(existing=stored_part),
            node,
            transfer.transfer_id,
            1,
            byte_offset=0,
            content_length=len(payload),
            part_sha256=digest,
            body=body_must_not_be_read(),
        )
    )
    assert after_cleanup.status == "already_received"


def _parts_for_payload(tmp_path: Path, transfer: OfflineTransfer, payload: bytes):
    split_at = (len(payload) + 1) // 2
    blocks = (payload[:split_at], payload[split_at:])
    transfer.compressed_size_bytes = len(payload)
    transfer.part_size_bytes = split_at
    transfer.total_parts = 2
    parts = []
    offset = 0
    for number, block in enumerate(blocks, start=1):
        path = tmp_path / "parts" / str(transfer.transfer_id) / f"{number:08d}.part"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(block)
        parts.append(
            SimpleNamespace(
                transfer_id=transfer.transfer_id,
                part_number=number,
                byte_offset=offset,
                size_bytes=len(block),
                sha256=hashlib.sha256(block).hexdigest(),
                file_path=str(path),
            )
        )
        offset += len(block)
    return parts


def test_complete_assembles_parts_validates_gzip_and_moves_to_ready(
    tmp_path,
    monkeypatch,
):
    uncompressed = b"lagoon_id,tag_id,bucket,state,value_num,value_bool,source\n"
    payload = gzip.compress(uncompressed)
    transfer = _transfer(row_count=1)
    transfer.uncompressed_size_bytes = len(uncompressed)
    transfer.sha256 = hashlib.sha256(payload).hexdigest()
    parts = _parts_for_payload(tmp_path, transfer, payload)
    node = SimpleNamespace(
        source_node_id=transfer.source_node_id,
        last_seen_at=None,
    )

    class Result:
        def all(self):
            return parts

    class FakeDb:
        def scalars(self, _statement):
            return Result()

        def commit(self):
            return None

        def rollback(self):
            return None

        def refresh(self, _value):
            return None

    monkeypatch.setattr(settings, "BACKFILL_STORAGE_PATH", tmp_path)

    completed = service._assemble_to_ready(
        FakeDb(),
        node,
        transfer,
    )

    assert completed.status == "READY"
    assert completed.received_at is not None
    assert Path(completed.assembled_path).read_bytes() == payload
    assert gzip.decompress(Path(completed.assembled_path).read_bytes()) == uncompressed


def test_complete_checksum_mismatch_preserves_failed_file(tmp_path, monkeypatch):
    uncompressed = b"minute csv\n"
    payload = gzip.compress(uncompressed)
    transfer = _transfer(row_count=1)
    transfer.uncompressed_size_bytes = len(uncompressed)
    transfer.sha256 = "0" * 64
    parts = _parts_for_payload(tmp_path, transfer, payload)
    node = SimpleNamespace(
        source_node_id=transfer.source_node_id,
        last_seen_at=None,
    )

    class Result:
        def all(self):
            return parts

    class FakeDb:
        def scalars(self, _statement):
            return Result()

        def commit(self):
            return None

        def rollback(self):
            return None

    monkeypatch.setattr(settings, "BACKFILL_STORAGE_PATH", tmp_path)

    with pytest.raises(service.TransferError) as error:
        service._assemble_to_ready(FakeDb(), node, transfer)

    assert error.value.code == "file_checksum_mismatch"
    assert not service.assembled_file_path(transfer.transfer_id).exists()
    assert service.failed_file_path(transfer.transfer_id).is_file()


def test_only_resumable_offline_transfer_routes_are_registered():
    from app.main import app

    routes = {
        (method, route.path)
        for route in app.routes
        for method in getattr(route, "methods", set())
    }
    assert ("POST", "/offline-transfer/transfers") in routes
    assert (
        "PUT",
        "/offline-transfer/transfers/{transfer_id}/parts/{part_number}",
    ) in routes
    assert (
        "POST",
        "/offline-transfer/transfers/{transfer_id}/complete",
    ) in routes
    assert ("GET", "/offline-transfer/transfers/{transfer_id}/status") in routes
    assert ("POST", "/ingest/offline/v1/backfill") not in routes
    assert all("/offline-backfill" not in path for _, path in routes)


def test_migration_is_userweb_safe_and_has_no_cagg_worker():
    migration = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "create_offline_transfer.sql"
    ).read_text(encoding="utf-8")

    assert "information_schema.columns" in migration
    assert "ALTER TABLE public.scada_minute\n    ADD COLUMN" not in migration
    assert "OWNER TO postgres" not in migration
    assert "refresh_continuous_aggregate" not in migration
    assert "'READY'" in migration
