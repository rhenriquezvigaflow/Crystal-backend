-- Continuous aggregates for SCADA history.
-- Run with: psql "$DATABASE_URL" -f scripts/sql/create_scada_continuous_aggregates.sql

CREATE MATERIALIZED VIEW IF NOT EXISTS public.scada_minute_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', bucket_ts) AS bucket,
    lagoon_id,
    tag_id,
    AVG(value_num) AS avg_val,
    MIN(value_num) AS min_val,
    MAX(value_num) AS max_val,
    COUNT(*) AS samples
FROM public.scada_minute
WHERE value_num IS NOT NULL
GROUP BY 1, 2, 3;

DO $$
BEGIN
  IF to_regclass('public.scada_minute_hourly') IS NOT NULL THEN
    PERFORM add_continuous_aggregate_policy(
      'public.scada_minute_hourly',
      start_offset => INTERVAL '7 days',
      end_offset => INTERVAL '1 hour',
      schedule_interval => INTERVAL '15 minutes'
    );
  END IF;
EXCEPTION
  WHEN duplicate_object THEN
    NULL;
END;
$$;

CREATE MATERIALIZED VIEW IF NOT EXISTS public.scada_minute_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', bucket_ts) AS bucket,
    lagoon_id,
    tag_id,
    AVG(value_num) AS avg_val,
    MIN(value_num) AS min_val,
    MAX(value_num) AS max_val,
    COUNT(*) AS samples
FROM public.scada_minute
WHERE value_num IS NOT NULL
GROUP BY 1, 2, 3;

DO $$
BEGIN
  IF to_regclass('public.scada_minute_daily') IS NOT NULL THEN
    PERFORM add_continuous_aggregate_policy(
      'public.scada_minute_daily',
      start_offset => INTERVAL '90 days',
      end_offset => INTERVAL '1 day',
      schedule_interval => INTERVAL '1 hour'
    );
  END IF;
EXCEPTION
  WHEN duplicate_object THEN
    NULL;
END;
$$;

CREATE MATERIALIZED VIEW IF NOT EXISTS public.scada_minute_weekly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 week', bucket_ts) AS bucket,
    lagoon_id,
    tag_id,
    AVG(value_num) AS avg_val,
    MIN(value_num) AS min_val,
    MAX(value_num) AS max_val,
    COUNT(*) AS samples
FROM public.scada_minute
WHERE value_num IS NOT NULL
GROUP BY 1, 2, 3;

DO $$
BEGIN
  IF to_regclass('public.scada_minute_weekly') IS NOT NULL THEN
    PERFORM add_continuous_aggregate_policy(
      'public.scada_minute_weekly',
      start_offset => INTERVAL '2 years',
      end_offset => INTERVAL '1 week',
      schedule_interval => INTERVAL '1 day'
    );
  END IF;
EXCEPTION
  WHEN duplicate_object THEN
    NULL;
END;
$$;
