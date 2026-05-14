BEGIN;

INSERT INTO public.lagoons (
  id,
  name,
  plc_type,
  timezone,
  ip,
  enable,
  product_type,
  created_at
)
SELECT
  'central_hub_dubai',
  'Central Hub / Dubai',
  plc_type,
  timezone,
  ip,
  enable,
  product_type,
  created_at
FROM public.lagoons
WHERE id = 'central_district_dubai'
ON CONFLICT (id) DO UPDATE
SET
  name = EXCLUDED.name,
  plc_type = EXCLUDED.plc_type,
  timezone = EXCLUDED.timezone,
  ip = EXCLUDED.ip,
  enable = EXCLUDED.enable,
  product_type = EXCLUDED.product_type;

UPDATE public.scada_minute
SET lagoon_id = 'central_hub_dubai'
WHERE lagoon_id = 'central_district_dubai';

UPDATE public.scada_event
SET lagoon_id = 'central_hub_dubai'
WHERE lagoon_id = 'central_district_dubai';

UPDATE public.alarm_definition
SET lagoon_id = 'central_hub_dubai'
WHERE lagoon_id = 'central_district_dubai';

UPDATE public.alarm_event
SET lagoon_id = 'central_hub_dubai'
WHERE lagoon_id = 'central_district_dubai';

UPDATE public.alarm_notification_rule
SET lagoon_id = 'central_hub_dubai'
WHERE lagoon_id = 'central_district_dubai';

UPDATE public.collector_tag_registry
SET lagoon_id = 'central_hub_dubai'
WHERE lagoon_id = 'central_district_dubai';

UPDATE public.lagoon_layout_mapping
SET lagoon_id = 'central_hub_dubai'
WHERE lagoon_id = 'central_district_dubai';

DELETE FROM public.lagoons
WHERE id = 'central_district_dubai';

COMMIT;
