# Flujo de Insercion y Publicacion SCADA

**Version doc:** 1.3
**Actualizado:** 2026-04-07

---

## 1) Entrada de datos

Endpoint:

- `POST /ingest/scada`

Requisitos:

- Header `x-api-key` valido.
- Body JSON con `lagoon_id`, `timestamp` opcional y `tags`.

Ejemplo:

```json
{
  "lagoon_id": "laguna_1",
  "timestamp": "2026-03-13T14:30:45Z",
  "tags": {
    "bomba_1": 1,
    "temperatura": 28.5
  }
}
```

---

## 2) Secuencia de procesamiento

1. `ingest_scada` valida API key y payload.
2. Normaliza timestamp a UTC.
3. Ejecuta persistencia en thread con timeout (`INGEST_TIMEOUT_SEC`).
4. `ingest_service.ingest(...)`:
   - detecta cambios de estado por tag,
   - cierra evento abierto y crea nuevo evento,
   - flushea minutos cerrados en `scada_minute` (upsert por lote).
5. Se evalua motor de alarmas:
   - `evaluate_alarms(...)` para `state`, `comm_loss` y `threshold`.
   - abre/cierra en `alarm_event` segun reglas activas en `alarm_definition`.
6. Se enrutan notificaciones:
   - solo en transicion `OPEN` (una vez por evento),
   - reglas desde `alarm_notification_rule`.
7. Se actualiza `RealtimeStateStore`.
8. Se emite `tick` via websocket para esa laguna.
9. Respuesta `200 {"ok": true}`.

Errores esperables:

- `401` API key invalida.
- `422` payload invalido.
- `504` timeout ingest.
- `500` error interno.

---

## 3) Estado en memoria

`RealtimeStateStore` conserva:

- `tags` por laguna.
- `last_ts`.
- `pump_last_on`.
- `start_ts`.
- `timezone`.

En cada payload websocket se agregan:

- `plc_status` (`online`/`offline`).
- `local_time` (segun timezone de la laguna).

---

## 4) Bootstrap al iniciar

En `lifespan`:

1. Carga timezone desde tabla `lagoons`.
2. Detecta lagunas presentes en `scada_event`.
3. Precarga `pump_last_on` por tag desde `vw_scada_last_3_pump_actions`.
4. Inicia `ScadaStallWatchdog`.
5. Inicia monitoreo de `comm_loss` por laguna (reloj de servidor).

Objetivo: evitar que websocket arranque sin contexto de estado.

---

## 5) Lecturas REST asociadas

SCADA general:

- `GET /scada/{lagoon_id}/last-minute`
- `GET /scada/{lagoon_id}/current`
- `GET /scada/{lagoon_id}/pump-events/last-3`
- `GET /scada/history/{resolution}`

Producto Crystal:

- `GET /api/crystal/lagoons/{lagoon_id}/last-minute`
- `GET /api/crystal/lagoons/{lagoon_id}/current`
- `GET /api/crystal/lagoons/{lagoon_id}/pump-events/last-3`
- `GET /api/crystal/history`

Producto Small:

- `GET /api/small/lagoons/{lagoon_id}/last-minute`
- `GET /api/small/lagoons/{lagoon_id}/current`
- `GET /api/small/lagoons/{lagoon_id}/pump-events/last-3`
- `GET /api/small/history`

Alarmas PT/FIT (umbrales):

- `GET /alarms/{lagoon_id}/thresholds/pt-fit/view` (recomendado frontend)
- `PUT /alarms/{lagoon_id}/thresholds/pt-fit`

---

## 6) Flujo de historico agregado

Implementacion: `app/scada/history/repo.py`.

Reglas:

1. Resolution valida: `hourly|daily|weekly`.
2. Si `end_date < start_date`, el backend invierte el rango.
3. Si existe vista continua (`scada_minute_<resolution>`): `source = "view"`.
4. Si no existe: fallback con `time_bucket` sobre `scada_minute` (`source = "table"`).
5. Respuesta: `lagoon_id`, `resolution`, `source`, `series[{tag, points}]`.

---

## 7) Flujo de umbrales PT/FIT (actual)

1. Frontend consulta `GET /alarms/{lagoon_id}/thresholds/pt-fit/view`.
2. Backend responde filas consolidadas por `tag_id`:
   - `tag_id`, `tag_name`, `source`,
   - `min_value`, `max_value`,
   - `severity`, `enabled`.
3. Frontend guarda con `PUT /alarms/{lagoon_id}/thresholds/pt-fit`.
4. Cada item puede crear o actualizar codigos:
   - `threshold_<tag>_min`
   - `threshold_<tag>_max`
5. Validaciones de negocio:
   - `tag_id` inicia con `PT` o `FIT`,
   - al menos uno: `min_value` o `max_value`,
   - si ambos vienen: `min_value < max_value`,
   - `severity` valida (`info|warning|critical`).

Nota:

- La vista consolidada de lectura de umbrales esta optimizada y no devuelve:
  - `last_value`
  - `last_ts`
  - `updated_at`

---

## 8) WebSocket operativo

Endpoints:

- `WS /ws/scada?lagoon_id=<id>&token=<jwt>`
- `WS /ws/scada/{lagoon_id}?token=<jwt>`
- `WS /ws/crystal/{lagoon_id}?token=<jwt>`
- `WS /ws/small/{lagoon_id}?token=<jwt>`

Flujo:

1. Se valida token JWT.
2. Se valida permiso `can_view` para la laguna.
3. Se envia `snapshot` inicial.
4. Se mantienen ticks en cada ingest.

---

## 9) Dependencias de seguridad

Para que RBAC funcione en REST y WS deben existir:

- tablas `users`, `roles`, `user_roles`.
- vista `vw_user_lagoons` con columnas:
  - `user_id`
  - `lagoon_id`
  - `can_view`
  - `can_edit`
  - `can_control`

Scripts disponibles:

- `scripts/sql/create_rbac_tables.sql`
- `scripts/seed_roles.py`

---

## 10) Guia rapida: alta de laguna + alertas

## 10.1) Alta/actualizacion de laguna

```sql
INSERT INTO lagoons (
    id,
    name,
    plc_type,
    timezone,
    ip,
    scada_layout,
    product_type
) VALUES (
    'laguna_nueva',
    'Laguna Nueva',
    'siemens',
    'America/Santiago',
    '10.10.10.50',
    'layout1',
    'crystal'
)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    plc_type = EXCLUDED.plc_type,
    timezone = EXCLUDED.timezone,
    ip = EXCLUDED.ip,
    scada_layout = EXCLUDED.scada_layout,
    product_type = EXCLUDED.product_type;
```

Verificacion:

```sql
SELECT id, name, timezone, scada_layout, product_type
FROM lagoons
WHERE id = 'laguna_nueva';
```

## 10.2) Verificar que llega telemetria

```sql
SELECT 'scada_event' AS source, COUNT(*) AS rows_count
FROM scada_event
WHERE lagoon_id = 'laguna_nueva'
UNION ALL
SELECT 'scada_minute' AS source, COUNT(*) AS rows_count
FROM scada_minute
WHERE lagoon_id = 'laguna_nueva';
```

## 10.3) Crear alarma base de comm_loss por laguna (critical)

```sql
INSERT INTO alarm_definition (
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
    last_seen_ts,
    created_at,
    updated_at
)
VALUES (
    gen_random_uuid(),
    'laguna_nueva',
    NULL,
    'lagoon_laguna_nueva_no_signal_10m',
    'Laguna laguna_nueva sin senal 10 minutos',
    'Se activa cuando la laguna no recibe datos por mas de 10 minutos.',
    'comm_loss',
    'critical',
    TRUE,
    '{"timeout_sec": 600}'::jsonb,
    NULL,
    NOW(),
    NOW()
)
ON CONFLICT (lagoon_id, code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    alarm_type = EXCLUDED.alarm_type,
    severity = EXCLUDED.severity,
    enabled = EXCLUDED.enabled,
    condition = EXCLUDED.condition,
    updated_at = NOW();
```

## 10.4) Regla de notificacion para esa laguna

```sql
INSERT INTO alarm_notification_rule (
    id,
    enabled,
    scope,
    lagoon_id,
    alarm_definition_id,
    alarm_type,
    severity,
    tag_pattern,
    channel,
    target,
    created_at,
    updated_at
)
SELECT
    gen_random_uuid(),
    TRUE,
    'lagoon',
    'laguna_nueva',
    NULL,
    'comm_loss',
    'critical',
    NULL,
    'email',
    'scada-alertas@tu-dominio.com',
    NOW(),
    NOW()
WHERE NOT EXISTS (
    SELECT 1
    FROM alarm_notification_rule r
    WHERE
        r.scope = 'lagoon'
        AND r.lagoon_id = 'laguna_nueva'
        AND r.alarm_type = 'comm_loss'
        AND r.severity = 'critical'
        AND r.channel = 'email'
        AND r.target = 'scada-alertas@tu-dominio.com'
);
```

## 10.5) Alta de umbral PT/FIT (recomendado por API)

```bash
curl -k -X PUT "https://localhost/alarms/laguna_nueva/thresholds/pt-fit" \
  -H "Authorization: Bearer <JWT_BEARER_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {
        "tag_id": "PT117_R_SCADA",
        "min_value": 1.2,
        "max_value": 8.5,
        "severity": "critical",
        "enabled": true
      }
    ]
  }'
```

## 10.6) Verificacion operacional de alertas

```sql
SELECT alarm_type, severity, enabled, COUNT(*) AS definitions_count
FROM alarm_definition
WHERE lagoon_id = 'laguna_nueva'
GROUP BY alarm_type, severity, enabled
ORDER BY alarm_type, severity;
```

```sql
SELECT status, alarm_type, severity, tag_id, opened_at, closed_at
FROM alarm_event
WHERE lagoon_id = 'laguna_nueva'
ORDER BY opened_at DESC
LIMIT 20;
```

## 10.7) Verificacion de permisos por laguna (RBAC)

```sql
SELECT user_id, lagoon_id, can_view, can_edit, can_control
FROM vw_user_lagoons
WHERE lagoon_id = 'laguna_nueva'
ORDER BY user_id;
```
