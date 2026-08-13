-- Additive, idempotent central migration for resumable Collector Offline files.
-- It deliberately does not rewrite historical scada_minute rows: this table is
-- a large TimescaleDB hypertable and most existing rows currently have no source.
BEGIN;

CREATE TABLE IF NOT EXISTS public.offline_collector_node (
    source_node_id varchar(128) PRIMARY KEY,
    lagoon_id varchar(64) NOT NULL REFERENCES public.lagoons(id) ON DELETE CASCADE,
    token_hash varchar(64) NOT NULL UNIQUE,
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz,
    CONSTRAINT ck_offline_collector_node_token_hash
        CHECK (token_hash ~ '^[0-9a-f]{64}$')
);

CREATE INDEX IF NOT EXISTS ix_offline_collector_node_lagoon
    ON public.offline_collector_node (lagoon_id);
CREATE INDEX IF NOT EXISTS ix_offline_collector_node_enabled
    ON public.offline_collector_node (enabled);

-- On the live database this column already exists. The conditional dynamic
-- ALTER avoids requiring table ownership when this migration runs as userweb.
DO $migration$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'scada_minute'
          AND column_name = 'source'
    ) THEN
        EXECUTE 'ALTER TABLE public.scada_minute '
             || 'ADD COLUMN source varchar(30)';
    END IF;
END;
$migration$;

CREATE TABLE IF NOT EXISTS public.offline_transfer (
    transfer_id uuid PRIMARY KEY,
    chunk_id uuid NOT NULL,
    schema_version integer NOT NULL,
    data_kind varchar(16) NOT NULL,
    source varchar(32) NOT NULL DEFAULT 'collector_offline',
    source_node_id varchar(128) NOT NULL
        REFERENCES public.offline_collector_node(source_node_id) ON DELETE RESTRICT,
    lagoon_id varchar(64) NOT NULL
        REFERENCES public.lagoons(id) ON DELETE RESTRICT,
    sequence_number bigint NOT NULL,
    file_name varchar(255) NOT NULL,
    format varchar(8) NOT NULL,
    compression varchar(8) NOT NULL,
    row_count integer NOT NULL,
    uncompressed_size_bytes bigint NOT NULL,
    compressed_size_bytes bigint NOT NULL,
    part_size_bytes integer NOT NULL,
    total_parts integer NOT NULL,
    from_timestamp timestamptz NOT NULL,
    to_timestamp timestamptz NOT NULL,
    sha256 varchar(64) NOT NULL,
    manifest jsonb NOT NULL,
    status varchar(20) NOT NULL DEFAULT 'UPLOADING',
    assembled_path text,
    staged_rows integer,
    inserted_rows integer,
    duplicate_rows integer,
    retry_count integer NOT NULL DEFAULT 0,
    next_retry_at timestamptz,
    lease_owner varchar(128),
    lease_expires_at timestamptz,
    last_error_code varchar(64),
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    received_at timestamptz,
    import_started_at timestamptz,
    verified_at timestamptz,
    quarantined_at timestamptz,
    files_cleaned_at timestamptz,
    CONSTRAINT uq_offline_transfer_chunk_id UNIQUE (chunk_id),
    CONSTRAINT uq_offline_transfer_node_sequence
        UNIQUE (source_node_id, sequence_number),
    CONSTRAINT ck_offline_transfer_schema_version CHECK (schema_version = 1),
    CONSTRAINT ck_offline_transfer_source CHECK (source = 'collector_offline'),
    CONSTRAINT ck_offline_transfer_data_kind CHECK (data_kind = 'minute'),
    CONSTRAINT ck_offline_transfer_format CHECK (format = 'csv'),
    CONSTRAINT ck_offline_transfer_compression CHECK (compression = 'gzip'),
    CONSTRAINT ck_offline_transfer_status CHECK (
        status IN (
            'UPLOADING', 'READY', 'IMPORTING',
            'VERIFIED', 'FAILED', 'QUARANTINED'
        )
    ),
    CONSTRAINT ck_offline_transfer_positive_sizes CHECK (
        row_count > 0
        AND uncompressed_size_bytes > 0
        AND compressed_size_bytes > 0
        AND part_size_bytes > 0
        AND total_parts > 0
    ),
    CONSTRAINT ck_offline_transfer_part_count CHECK (
        total_parts = (
            (compressed_size_bytes + part_size_bytes - 1) / part_size_bytes
        )
    ),
    CONSTRAINT ck_offline_transfer_timestamp_range
        CHECK (from_timestamp <= to_timestamp),
    CONSTRAINT ck_offline_transfer_sha256
        CHECK (sha256 ~ '^[0-9a-f]{64}$')
);

CREATE INDEX IF NOT EXISTS ix_offline_transfer_status
    ON public.offline_transfer (status, created_at);
CREATE INDEX IF NOT EXISTS ix_offline_transfer_node_created
    ON public.offline_transfer (source_node_id, created_at);

CREATE TABLE IF NOT EXISTS public.offline_transfer_part (
    transfer_id uuid NOT NULL
        REFERENCES public.offline_transfer(transfer_id) ON DELETE CASCADE,
    part_number integer NOT NULL,
    byte_offset bigint NOT NULL,
    size_bytes integer NOT NULL,
    sha256 varchar(64) NOT NULL,
    file_path text NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (transfer_id, part_number),
    CONSTRAINT uq_offline_transfer_part_offset
        UNIQUE (transfer_id, byte_offset),
    CONSTRAINT ck_offline_transfer_part_number CHECK (part_number > 0),
    CONSTRAINT ck_offline_transfer_part_size
        CHECK (byte_offset >= 0 AND size_bytes > 0),
    CONSTRAINT ck_offline_transfer_part_sha256
        CHECK (sha256 ~ '^[0-9a-f]{64}$')
);

-- Upgrade an earlier draft without losing received parts.
ALTER TABLE public.offline_transfer
    DROP CONSTRAINT IF EXISTS ck_offline_transfer_status;
UPDATE public.offline_transfer
SET status = 'READY'
WHERE status = 'UPLOADED';
ALTER TABLE public.offline_transfer
    ADD CONSTRAINT ck_offline_transfer_status CHECK (
        status IN (
            'UPLOADING', 'READY', 'IMPORTING',
            'VERIFIED', 'FAILED', 'QUARANTINED'
        )
    );

COMMIT;

-- Provision node tokens separately. Never store plaintext tokens in this file.
