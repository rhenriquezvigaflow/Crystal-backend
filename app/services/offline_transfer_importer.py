from __future__ import annotations

import csv
import gzip
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.offline_transfer import OFFLINE_SOURCE, OfflineTransfer
from app.models.scada_minute import COLLECTOR_OFFLINE_SOURCE


MINUTE_CSV_HEADER = (
    "lagoon_id",
    "tag_id",
    "bucket",
    "state",
    "value_num",
    "value_bool",
    "source",
)
EVENT_CSV_HEADER = (
    "id",
    "lagoon_id",
    "tag_id",
    "tag_label",
    "alert_type",
    "previous_state",
    "state",
    "start_ts",
    "end_ts",
    "duration_sec",
    "source",
)
_TZ_SUFFIX = re.compile(r"(?:Z|[+-][0-9]{2}:[0-9]{2})$")


class OfflineTransferImportError(Exception):
    def __init__(self, code: str, detail: str, *, permanent: bool = True) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.permanent = permanent


@dataclass(frozen=True)
class CsvValidationSummary:
    row_count: int
    from_timestamp: datetime
    to_timestamp: datetime


@dataclass(frozen=True)
class ImportCounts:
    staged_rows: int
    inserted_rows: int
    duplicate_rows: int


def _error(code: str, detail: str) -> OfflineTransferImportError:
    return OfflineTransferImportError(code, detail, permanent=True)


def _parse_utc_timestamp(raw: str, field: str, row_number: int) -> datetime:
    if not raw or not _TZ_SUFFIX.search(raw):
        raise _error("invalid_timestamp", f"row {row_number} {field} needs UTC offset")
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        value = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise _error(
            "invalid_timestamp", f"row {row_number} {field} is not ISO-8601"
        ) from exc
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise _error("invalid_timestamp", f"row {row_number} {field} must be UTC")
    return value.astimezone(timezone.utc)


def _parse_int(raw: str, field: str, row_number: int, *, required: bool) -> int | None:
    if raw == "":
        if required:
            raise _error("invalid_integer", f"row {row_number} {field} is required")
        return None
    try:
        return int(raw, 10)
    except ValueError as exc:
        raise _error("invalid_integer", f"row {row_number} {field} is invalid") from exc


def _validate_minute_row(
    row: list[str],
    row_number: int,
    transfer: OfflineTransfer,
) -> tuple[datetime, str]:
    if len(row) != len(MINUTE_CSV_HEADER):
        raise _error("invalid_column_count", f"row {row_number} has wrong column count")
    lagoon_id, tag_id, bucket_raw, state_raw, number_raw, bool_raw, source = row
    if lagoon_id != transfer.lagoon_id:
        raise _error("lagoon_mismatch", f"row {row_number} lagoon differs from manifest")
    if not tag_id or len(tag_id) > 128:
        raise _error("invalid_tag", f"row {row_number} tag_id is invalid")
    if source != OFFLINE_SOURCE:
        raise _error("invalid_source", f"row {row_number} source must be collector_offline")
    bucket = _parse_utc_timestamp(bucket_raw, "bucket", row_number)
    if bucket.second or bucket.microsecond:
        raise _error("unaligned_bucket", f"row {row_number} bucket is not minute-aligned")

    populated = sum(value != "" for value in (state_raw, number_raw, bool_raw))
    if populated != 1:
        raise _error(
            "invalid_typed_value",
            f"row {row_number} needs exactly one typed value",
        )
    if state_raw:
        state = _parse_int(state_raw, "state", row_number, required=True)
        if state is None or not -32768 <= state <= 32767:
            raise _error("invalid_state", f"row {row_number} state exceeds smallint")
    if number_raw:
        try:
            number = float(number_raw)
        except ValueError as exc:
            raise _error("invalid_number", f"row {row_number} value_num is invalid") from exc
        if not math.isfinite(number):
            raise _error("invalid_number", f"row {row_number} value_num is not finite")
    if bool_raw and bool_raw not in {"true", "false"}:
        raise _error(
            "invalid_boolean",
            f"row {row_number} value_bool must be true or false",
        )
    return bucket, tag_id


def _validate_event_row(
    row: list[str],
    row_number: int,
    transfer: OfflineTransfer,
) -> tuple[datetime, str, str]:
    if len(row) != len(EVENT_CSV_HEADER):
        raise _error("invalid_column_count", f"row {row_number} has wrong column count")
    (
        event_id,
        lagoon_id,
        tag_id,
        tag_label,
        alert_type,
        previous_state_raw,
        state_raw,
        start_raw,
        end_raw,
        duration_raw,
        source,
    ) = row
    try:
        UUID(event_id)
    except ValueError as exc:
        raise _error("invalid_event_id", f"row {row_number} id is not UUID") from exc
    if lagoon_id != transfer.lagoon_id:
        raise _error("lagoon_mismatch", f"row {row_number} lagoon differs from manifest")
    if not tag_id or len(tag_id) > 128 or len(tag_label) > 255:
        raise _error("invalid_tag", f"row {row_number} tag metadata is invalid")
    if alert_type != "STATE_CHANGE":
        raise _error("invalid_alert_type", f"row {row_number} alert_type is invalid")
    if source != OFFLINE_SOURCE:
        raise _error("invalid_source", f"row {row_number} source must be collector_offline")
    _parse_int(previous_state_raw, "previous_state", row_number, required=False)
    _parse_int(state_raw, "state", row_number, required=True)
    start_ts = _parse_utc_timestamp(start_raw, "start_ts", row_number)
    end_ts = _parse_utc_timestamp(end_raw, "end_ts", row_number) if end_raw else None
    duration = _parse_int(duration_raw, "duration_sec", row_number, required=False)
    if end_ts is not None and end_ts < start_ts:
        raise _error("invalid_event_period", f"row {row_number} end precedes start")
    if duration is not None and duration < 0:
        raise _error("invalid_duration", f"row {row_number} duration is negative")
    if end_ts is None and duration is not None:
        raise _error(
            "invalid_event_period",
            f"row {row_number} duration requires end_ts",
        )
    return start_ts, tag_id, event_id


def validate_csv_gzip(path: Path, transfer: OfflineTransfer) -> CsvValidationSummary:
    expected_header = (
        MINUTE_CSV_HEADER if transfer.data_kind == "minute" else EVENT_CSV_HEADER
    )
    row_count = 0
    first_timestamp: datetime | None = None
    last_timestamp: datetime | None = None
    previous_key: tuple | None = None
    try:
        with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
            reader = csv.reader(stream, strict=True)
            try:
                header = tuple(next(reader))
            except StopIteration as exc:
                raise _error("empty_csv", "CSV is empty") from exc
            if header != expected_header:
                raise _error(
                    "invalid_csv_header",
                    f"expected header {','.join(expected_header)}",
                )
            for row_count, row in enumerate(reader, start=1):
                csv_row_number = row_count + 1
                if transfer.data_kind == "minute":
                    timestamp, tag_id = _validate_minute_row(
                        row, csv_row_number, transfer
                    )
                    key = (timestamp, tag_id)
                else:
                    timestamp, tag_id, event_id = _validate_event_row(
                        row, csv_row_number, transfer
                    )
                    key = (timestamp, tag_id, event_id)
                if previous_key is not None and key <= previous_key:
                    raise _error(
                        "non_deterministic_order",
                        f"row {csv_row_number} is not strictly ordered",
                    )
                previous_key = key
                first_timestamp = first_timestamp or timestamp
                last_timestamp = timestamp
    except (gzip.BadGzipFile, EOFError, OSError, UnicodeError, csv.Error) as exc:
        if isinstance(exc, OfflineTransferImportError):
            raise
        raise _error("invalid_csv_gzip", "cannot decode CSV.gz") from exc

    if row_count != transfer.row_count:
        raise _error(
            "row_count_mismatch",
            f"CSV has {row_count} rows but manifest declares {transfer.row_count}",
        )
    if first_timestamp is None or last_timestamp is None:
        raise _error("empty_csv", "CSV has no data rows")
    manifest_from = transfer.from_timestamp.astimezone(timezone.utc)
    manifest_to = transfer.to_timestamp.astimezone(timezone.utc)
    if first_timestamp != manifest_from or last_timestamp != manifest_to:
        raise _error(
            "timestamp_range_mismatch",
            "CSV timestamp range differs from manifest",
        )
    return CsvValidationSummary(row_count, first_timestamp, last_timestamp)


def _raw_cursor(db: Session):
    return db.connection().connection.cursor()


def _set_import_timeouts(cursor) -> None:
    cursor.execute(
        "SELECT set_config('statement_timeout', %s, true)",
        (str(settings.BACKFILL_IMPORT_STATEMENT_TIMEOUT_MS),),
    )


def _copy_gzip(cursor, path: Path, copy_sql: str) -> None:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
        cursor.copy_expert(copy_sql, stream)


def _validate_common_stage(cursor, transfer: OfflineTransfer, table: str) -> int:
    cursor.execute(f"SELECT count(*) FROM {table}")
    staged_rows = int(cursor.fetchone()[0])
    if staged_rows != transfer.row_count:
        raise _error("staged_row_count_mismatch", "staging row count differs from manifest")
    cursor.execute(
        f"SELECT count(*) FROM {table} WHERE lagoon_id <> %s OR source <> %s",
        (transfer.lagoon_id, OFFLINE_SOURCE),
    )
    if int(cursor.fetchone()[0]):
        raise _error("stage_scope_mismatch", "staging contains another lagoon or source")
    cursor.execute(
        f"""
        SELECT count(*)
        FROM {table} stage
        LEFT JOIN public.collector_tag_registry registry
          ON registry.lagoon_id = stage.lagoon_id
         AND registry.tag_id = stage.tag_id
        WHERE registry.tag_id IS NULL
        """
    )
    if int(cursor.fetchone()[0]):
        raise _error("unknown_tag", "staging contains an unregistered tag")
    return staged_rows


def _import_minutes(db: Session, path: Path, transfer: OfflineTransfer) -> ImportCounts:
    with _raw_cursor(db) as cursor:
        _set_import_timeouts(cursor)
        cursor.execute(
            """
            CREATE TEMP TABLE staging_scada_minute_offline (
                lagoon_id text NOT NULL,
                tag_id text NOT NULL,
                bucket timestamptz NOT NULL,
                state smallint,
                value_num double precision,
                value_bool boolean,
                source varchar(32) NOT NULL,
                CONSTRAINT ck_transfer_stage_minute_source
                    CHECK (source = 'collector_offline'),
                CONSTRAINT ck_transfer_stage_minute_value
                    CHECK (num_nonnulls(state, value_num, value_bool) = 1)
            ) ON COMMIT DROP
            """
        )
        _copy_gzip(
            cursor,
            path,
            """
            COPY staging_scada_minute_offline
                (lagoon_id, tag_id, bucket, state, value_num, value_bool, source)
            FROM STDIN WITH (FORMAT CSV, HEADER TRUE, NULL '')
            """,
        )
        staged_rows = _validate_common_stage(
            cursor, transfer, "staging_scada_minute_offline"
        )
        cursor.execute(
            """
            SELECT count(*) FROM (
                SELECT lagoon_id, tag_id, bucket
                FROM staging_scada_minute_offline
                GROUP BY lagoon_id, tag_id, bucket
                HAVING count(*) > 1
            ) duplicates
            """
        )
        if int(cursor.fetchone()[0]):
            raise _error("duplicate_csv_key", "CSV repeats a minute natural key")
        cursor.execute(
            f"""
            INSERT INTO public.scada_minute
                (lagoon_id, tag_id, bucket, state, value_num, value_bool, source)
            SELECT lagoon_id, tag_id, bucket, state, value_num, value_bool,
                   '{COLLECTOR_OFFLINE_SOURCE}'
            FROM staging_scada_minute_offline
            ORDER BY bucket, tag_id
            ON CONFLICT (lagoon_id, tag_id, bucket) DO NOTHING
            """
        )
        inserted_rows = max(int(cursor.rowcount), 0)
    return ImportCounts(staged_rows, inserted_rows, staged_rows - inserted_rows)


def _import_events(db: Session, path: Path, transfer: OfflineTransfer) -> ImportCounts:
    with _raw_cursor(db) as cursor:
        _set_import_timeouts(cursor)
        cursor.execute(
            """
            CREATE TEMP TABLE offline_transfer_event_stage (
                id uuid PRIMARY KEY,
                lagoon_id text NOT NULL,
                tag_id text NOT NULL,
                tag_label text,
                alert_type text NOT NULL,
                previous_state integer,
                state integer NOT NULL,
                start_ts timestamptz NOT NULL,
                end_ts timestamptz,
                duration_sec integer,
                source varchar(32) NOT NULL,
                CONSTRAINT ck_transfer_stage_event_source
                    CHECK (source = 'collector_offline'),
                CONSTRAINT ck_transfer_stage_event_period
                    CHECK (
                        (end_ts IS NULL AND duration_sec IS NULL)
                        OR (
                            end_ts IS NOT NULL
                            AND (duration_sec IS NULL OR duration_sec >= 0)
                        )
                    )
            ) ON COMMIT DROP
            """
        )
        _copy_gzip(
            cursor,
            path,
            """
            COPY offline_transfer_event_stage
                (id, lagoon_id, tag_id, tag_label, alert_type, previous_state,
                 state, start_ts, end_ts, duration_sec, source)
            FROM STDIN WITH (FORMAT CSV, HEADER TRUE, NULL '')
            """,
        )
        staged_rows = _validate_common_stage(
            cursor, transfer, "offline_transfer_event_stage"
        )
        cursor.execute(
            """
            SELECT count(*)
            FROM offline_transfer_event_stage stage
            JOIN public.scada_event target ON target.id = stage.id
            WHERE target.lagoon_id IS DISTINCT FROM stage.lagoon_id
               OR target.tag_id IS DISTINCT FROM stage.tag_id
               OR target.start_ts IS DISTINCT FROM stage.start_ts
               OR target.state IS DISTINCT FROM stage.state
               OR (
                    target.end_ts IS NOT NULL
                AND target.end_ts IS DISTINCT FROM stage.end_ts
               )
            """
        )
        if int(cursor.fetchone()[0]):
            raise _error(
                "event_identity_conflict",
                "event UUID already identifies different immutable data",
            )
        cursor.execute(
            """
            UPDATE public.scada_event target
            SET end_ts = stage.end_ts,
                duration_sec = stage.duration_sec,
                source = COALESCE(target.source, stage.source)
            FROM offline_transfer_event_stage stage
            WHERE target.id = stage.id
              AND target.end_ts IS NULL
              AND stage.end_ts IS NOT NULL
            """
        )
        updated_rows = max(int(cursor.rowcount), 0)
        cursor.execute(
            """
            INSERT INTO public.scada_event
                (id, lagoon_id, tag_id, tag_label, alert_type, previous_state,
                 state, start_ts, end_ts, duration_sec, source)
            SELECT id, lagoon_id, tag_id, COALESCE(tag_label, tag_id), alert_type,
                   previous_state, state, start_ts, end_ts, duration_sec,
                   'collector_offline'
            FROM offline_transfer_event_stage
            ORDER BY start_ts, tag_id, id
            ON CONFLICT (id) DO NOTHING
            """
        )
        new_rows = max(int(cursor.rowcount), 0)
        cursor.execute(
            """
            SELECT count(*)
            FROM offline_transfer_event_stage stage
            JOIN public.scada_event target ON target.id = stage.id
            """
        )
        reconciled_rows = int(cursor.fetchone()[0])
        if reconciled_rows != staged_rows:
            raise OfflineTransferImportError(
                "event_reconciliation_failed",
                "not every staged event exists after merge",
                permanent=False,
            )
    applied_rows = new_rows + updated_rows
    return ImportCounts(staged_rows, applied_rows, staged_rows - applied_rows)


def import_transfer(db: Session, transfer: OfflineTransfer) -> ImportCounts:
    if transfer.source != OFFLINE_SOURCE:
        raise _error("invalid_source", "transfer source is not collector_offline")
    if not transfer.assembled_path:
        raise OfflineTransferImportError(
            "assembled_file_missing",
            "transfer has no assembled path",
            permanent=False,
        )
    path = Path(transfer.assembled_path)
    if not path.is_file():
        raise OfflineTransferImportError(
            "assembled_file_missing",
            "assembled file does not exist",
            permanent=False,
        )
    validate_csv_gzip(path, transfer)
    if transfer.data_kind != "minute":
        raise _error("unsupported_data_kind", "only minute transfers are supported")
    return _import_minutes(db, path, transfer)
