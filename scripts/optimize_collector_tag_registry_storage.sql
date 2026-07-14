-- Optional storage optimization for collector_tag_registry.
--
-- Run as postgres/table owner in autocommit mode after deploying the v2 sync
-- function. The application-level fix does not depend on this script.

DROP INDEX CONCURRENTLY IF EXISTS public.ix_collector_tag_registry_lagoon_last_seen;

ALTER TABLE public.collector_tag_registry
    SET (
        fillfactor = 70,
        autovacuum_enabled = true,
        autovacuum_vacuum_threshold = 1000,
        autovacuum_vacuum_scale_factor = 0.0,
        autovacuum_analyze_threshold = 1000,
        autovacuum_analyze_scale_factor = 0.0
    );

VACUUM (FULL, ANALYZE) public.collector_tag_registry;
