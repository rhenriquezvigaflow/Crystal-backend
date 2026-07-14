-- Permanent, application-role deployable mitigation for
-- collector_tag_registry write amplification.
--
-- This v2 function deliberately has a new name so the application role can
-- install it without needing ownership of the legacy postgres-owned function.
-- Storage-level tuning that requires the postgres owner lives in the separate
-- optimize_collector_tag_registry_storage.sql maintenance script.

BEGIN;

CREATE OR REPLACE FUNCTION public.sp_sync_collector_tags_and_alarms_v2(
    p_lagoon_id text,
    p_source_ts timestamp with time zone,
    p_tags jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
AS $function$
DECLARE
    v_tag_id TEXT;
    v_tag_code TEXT;
    v_alarm_code TEXT;
    v_rows INTEGER := 0;
    v_registered_tags INTEGER := 0;
    v_new_alarm_definitions INTEGER := 0;
    v_lagoon_comm_loss_code TEXT;
    v_registry_refresh_interval CONSTANT INTERVAL := INTERVAL '30 seconds';
    v_sync_at TIMESTAMP WITH TIME ZONE := NOW();
BEGIN
    IF p_lagoon_id IS NULL OR BTRIM(p_lagoon_id) = '' THEN
        RAISE EXCEPTION
            'sp_sync_collector_tags_and_alarms requires lagoon_id';
    END IF;

    IF p_tags IS NULL OR jsonb_typeof(p_tags) <> 'object' THEN
        RETURN jsonb_build_object(
            'registered_tags', 0,
            'new_alarm_definitions', 0
        );
    END IF;

    v_lagoon_comm_loss_code := 'lagoon_'
        || REGEXP_REPLACE(LOWER(p_lagoon_id), '[^a-z0-9]+', '_', 'g')
        || '_no_signal_6h';

    INSERT INTO public.alarm_definition (
        id,
        lagoon_id,
        tag_id,
        code,
        name,
        description,
        alarm_type,
        severity,
        enabled,
        condition,
        created_at,
        updated_at
    )
    VALUES (
        gen_random_uuid(),
        p_lagoon_id,
        NULL,
        LEFT(v_lagoon_comm_loss_code, 128),
        LEFT('Laguna ' || p_lagoon_id || ' sin senal 6 horas', 255),
        'Auto-creada por sync de collector',
        'comm_loss',
        'critical',
        TRUE,
        '{"timeout_sec": 21600}'::jsonb,
        v_sync_at,
        v_sync_at
    )
    ON CONFLICT (lagoon_id, code) DO NOTHING;
    GET DIAGNOSTICS v_rows = ROW_COUNT;
    v_new_alarm_definitions := v_new_alarm_definitions + COALESCE(v_rows, 0);

    FOR v_tag_id IN
        SELECT BTRIM(key)
        FROM jsonb_each(p_tags)
    LOOP
        IF v_tag_id IS NULL OR v_tag_id = '' THEN
            CONTINUE;
        END IF;

        -- The NOT EXISTS predicate avoids touching a recent row during the
        -- normal one-second ingest cycle.  The ON CONFLICT predicate is the
        -- concurrency-safe backstop when two ingests race for the same tag.
        WITH inserted AS (
            INSERT INTO public.collector_tag_registry (
                lagoon_id,
                tag_id,
                first_seen_at,
                last_seen_at,
                last_source_ts,
                created_at,
                updated_at
            )
            SELECT
                p_lagoon_id,
                v_tag_id,
                v_sync_at,
                v_sync_at,
                p_source_ts,
                v_sync_at,
                v_sync_at
            WHERE NOT EXISTS (
                SELECT 1
                FROM public.collector_tag_registry AS current_registry
                WHERE current_registry.lagoon_id = p_lagoon_id
                  AND current_registry.tag_id = v_tag_id
                  AND current_registry.last_seen_at IS NOT NULL
                  AND current_registry.last_seen_at
                      > v_sync_at - v_registry_refresh_interval
            )
            ON CONFLICT (lagoon_id, tag_id) DO UPDATE
                SET last_seen_at = v_sync_at,
                    last_source_ts = COALESCE(
                        EXCLUDED.last_source_ts,
                        collector_tag_registry.last_source_ts
                    ),
                    updated_at = v_sync_at
            WHERE collector_tag_registry.last_seen_at IS NULL
               OR collector_tag_registry.last_seen_at
                    <= v_sync_at - v_registry_refresh_interval
            RETURNING xmax = 0 AS is_insert
        )
        SELECT
            CASE WHEN COALESCE(BOOL_OR(is_insert), FALSE) THEN 1 ELSE 0 END
        INTO v_rows
        FROM inserted;

        v_registered_tags := v_registered_tags + COALESCE(v_rows, 0);

        v_tag_code := REGEXP_REPLACE(LOWER(v_tag_id), '[^a-z0-9]+', '_', 'g');
        v_tag_code := TRIM(BOTH '_' FROM v_tag_code);
        IF v_tag_code = '' THEN
            v_tag_code := MD5(v_tag_id);
        END IF;
        v_tag_code := LEFT(v_tag_code, 90);

        IF UPPER(v_tag_id) ~ '^VE[0-9]+_ST$' THEN
            v_alarm_code := LEFT('state_' || v_tag_code || '_eq_3', 128);

            INSERT INTO public.alarm_definition (
                id,
                lagoon_id,
                tag_id,
                code,
                name,
                description,
                alarm_type,
                severity,
                enabled,
                condition,
                created_at,
                updated_at
            )
            VALUES (
                gen_random_uuid(),
                p_lagoon_id,
                v_tag_id,
                v_alarm_code,
                LEFT(v_tag_id || ' en estado 3', 255),
                'Auto-creada por sync de collector (valvula)',
                'state',
                'critical',
                TRUE,
                '{"equals": 3}'::jsonb,
                v_sync_at,
                v_sync_at
            )
            ON CONFLICT (lagoon_id, code) DO NOTHING;
            GET DIAGNOSTICS v_rows = ROW_COUNT;
            v_new_alarm_definitions := v_new_alarm_definitions + COALESCE(v_rows, 0);
        ELSIF UPPER(v_tag_id) ~ '^P[0-9]+(_ST|_STS_SCADA)$' THEN
            v_alarm_code := LEFT('state_' || v_tag_code || '_to_3', 128);

            INSERT INTO public.alarm_definition (
                id,
                lagoon_id,
                tag_id,
                code,
                name,
                description,
                alarm_type,
                severity,
                enabled,
                condition,
                created_at,
                updated_at
            )
            VALUES (
                gen_random_uuid(),
                p_lagoon_id,
                v_tag_id,
                v_alarm_code,
                LEFT(v_tag_id || ' cambia a falla', 255),
                'Auto-creada por sync de collector (bomba)',
                'state',
                'critical',
                TRUE,
                '{"from_states":[1,2], "to_state":3}'::jsonb,
                v_sync_at,
                v_sync_at
            )
            ON CONFLICT (lagoon_id, code) DO NOTHING;
            GET DIAGNOSTICS v_rows = ROW_COUNT;
            v_new_alarm_definitions := v_new_alarm_definitions + COALESCE(v_rows, 0);

            v_alarm_code := LEFT('comm_loss_' || v_tag_code || '_180s', 128);

            INSERT INTO public.alarm_definition (
                id,
                lagoon_id,
                tag_id,
                code,
                name,
                description,
                alarm_type,
                severity,
                enabled,
                condition,
                created_at,
                updated_at
            )
            VALUES (
                gen_random_uuid(),
                p_lagoon_id,
                v_tag_id,
                v_alarm_code,
                LEFT(v_tag_id || ' sin comunicacion 180 segundos', 255),
                'Auto-creada por sync de collector (bomba)',
                'comm_loss',
                'warning',
                TRUE,
                '{"timeout_sec": 180}'::jsonb,
                v_sync_at,
                v_sync_at
            )
            ON CONFLICT (lagoon_id, code) DO NOTHING;
            GET DIAGNOSTICS v_rows = ROW_COUNT;
            v_new_alarm_definitions := v_new_alarm_definitions + COALESCE(v_rows, 0);
        ELSIF
            UPPER(v_tag_id) ~ '^PT[0-9]+(_R)?(_SCADA)?$'
            OR UPPER(v_tag_id) ~ '^FIT[0-9]+(_R)?(_SCADA)?$'
            OR UPPER(v_tag_id) LIKE 'TOT_%'
            OR UPPER(v_tag_id) LIKE 'BACKWASH.%'
        THEN
            v_alarm_code := LEFT('comm_loss_' || v_tag_code || '_180s', 128);

            INSERT INTO public.alarm_definition (
                id,
                lagoon_id,
                tag_id,
                code,
                name,
                description,
                alarm_type,
                severity,
                enabled,
                condition,
                created_at,
                updated_at
            )
            VALUES (
                gen_random_uuid(),
                p_lagoon_id,
                v_tag_id,
                v_alarm_code,
                LEFT(v_tag_id || ' sin comunicacion 180 segundos', 255),
                'Auto-creada por sync de collector (analogico/totalizador)',
                'comm_loss',
                'warning',
                TRUE,
                '{"timeout_sec": 180}'::jsonb,
                v_sync_at,
                v_sync_at
            )
            ON CONFLICT (lagoon_id, code) DO NOTHING;
            GET DIAGNOSTICS v_rows = ROW_COUNT;
            v_new_alarm_definitions := v_new_alarm_definitions + COALESCE(v_rows, 0);
        END IF;
    END LOOP;

    RETURN jsonb_build_object(
        'registered_tags', v_registered_tags,
        'new_alarm_definitions', v_new_alarm_definitions
    );
END;
$function$;

COMMIT;
