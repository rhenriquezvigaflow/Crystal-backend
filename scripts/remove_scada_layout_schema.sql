-- Legacy SCADA layout cleanup.
-- This removes only layout/mapping structures and leaves historical SCADA data intact.

BEGIN;

DROP TABLE IF EXISTS public.lagoon_layout_mapping CASCADE;
DROP TABLE IF EXISTS public.layouts CASCADE;

ALTER TABLE public.lagoons
DROP COLUMN IF EXISTS scada_layout;

COMMIT;
