# Flujo de Insercion y Publicacion SCADA

**Version doc:** 1.5.0
**Actualizado:** 2026-04-09

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
  "lagoon_id": "costa_del_lago",
  "timestamp": "2026-04-09T18:20:00Z",
  "tags": {
    "PT117_R_SCADA": 2.31,
    "P006_STS_SCADA": 1
  }
}
```

---

## 2) Secuencia ingest

1. `ingest_scada` valida API key y payload.
2. Normaliza timestamp a UTC.
3. Ejecuta persistencia con timeout (`INGEST_TIMEOUT_SEC`).
4. `ingest_service.ingest(...)`:
   - detecta cambios de estado por tag,
   - cierra eventos abiertos,
   - crea eventos nuevos,
   - actualiza buckets en `scada_minute`.
5. Se evalua motor de alarmas.
6. Se despachan notificaciones post-commit cuando corresponde.
7. Se actualiza `RealtimeStateStore`.
8. Se emite `tick` via WebSocket.
9. Respuesta `200 {"ok": true}`.

Errores esperables:

- `401` API key invalida.
- `422` payload invalido.
- `504` timeout ingest.
- `500` error interno.

---

## 3) Estado realtime

`RealtimeStateStore` conserva por laguna:

- `tags` actuales.
- `last_ts`.
- `pump_last_on`.
- `start_ts`.
- `timezone`.
- `scada_layout` normalizado.

En cada payload WebSocket se agregan:

- `plc_status` (`online|offline`).
- `local_time` segun timezone de la laguna.
- `scada_layout` para alinear UI con backend.

---

## 4) Bootstrap al iniciar

En `lifespan`:

1. Carga lagunas habilitadas desde `lagoons`.
2. Precarga timezone y `scada_layout` por laguna.
3. Precarga `pump_last_on` desde `vw_scada_last_3_pump_actions`.
4. Inicia `ScadaStallWatchdog`.
5. Inicia `AlarmLagoonSignalMonitor`.

Objetivo: que el frontend reciba snapshot con contexto minimo aunque el collector este temporalmente desconectado.

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
- `GET|PUT /api/crystal/lagoons/{lagoon_id}/layout-config`

Producto Small:

- `GET /api/small/lagoons/{lagoon_id}/last-minute`
- `GET /api/small/lagoons/{lagoon_id}/current`
- `GET /api/small/lagoons/{lagoon_id}/pump-events/last-3`
- `GET /api/small/history`
- `GET|PUT /api/small/lagoons/{lagoon_id}/layout-config`

Alarmas PT/FIT:

- `GET /alarms/{lagoon_id}/thresholds/pt-fit/view`
- `PUT /alarms/{lagoon_id}/thresholds/pt-fit`

---

## 6) Flujo de historico

Implementacion: `app/scada/history/repo.py`.

Reglas:

1. Resolucion valida: `hourly|daily|weekly`.
2. Si `end_date < start_date`, se invierte el rango.
3. Si existe vista continua (`scada_minute_<resolution>`), `source = "view"`.
4. Si no existe, fallback con `time_bucket` sobre `scada_minute`, `source = "table"`.
5. Respuesta de producto y general: `series[{tag, points}]`.

Frontend compatible:

- acepta `tag`, `tag_key` o `name` para identificar cada serie.
- filtra tags no ploteables (`WM`, `_ST_`, `_STATUS`, `_BOOL`, `RETRO`).

---

## 7) Flujo layout SCADA dinamico

1. Frontend obtiene laguna desde `/api/{product}/lagoons` o `/lagoons`.
2. Frontend pide `GET /lagoons/{lagoon_id}/mapping`.
3. Backend resuelve `layout_id` desde `lagoons.scada_layout`.
4. Backend lee `lagoon_layout_mapping.mapping_json`.
5. Backend agrega `collector_tags` desde `collector_tag_registry`.
6. Frontend pide `GET /layouts/{layout_id}`.
7. Frontend combina `layout.json_definition.elements` + `mapping_json` + `collector_tags`.
8. Solo se muestran tarjetas cuyo tag esta habilitado por collector, salvo `always_visible=true`.
9. Si no hay realtime en 7 segundos, el frontend muestra el plano y las tarjetas con `--`.

---

## 8) Estados SVG de bombas y valvulas

Los valores discretos se interpretan asi:

- `0`: rojo.
- `1`: verde.
- `2`: azul.
- `3`: amarillo.
- sin dato: gris.

El backend solo entrega tags y mapping. La aplicacion de color se hace en frontend sobre el SVG usando `svg_target` y los tags realtime.

---

## 9) Flujo de umbrales PT/FIT

1. Frontend consulta `GET /alarms/{lagoon_id}/thresholds/pt-fit/view`.
2. Backend responde filas consolidadas por `tag_id`:
   - `tag_id`, `tag_name`, `source`, `min_value`, `max_value`, `severity`, `enabled`.
3. Frontend guarda con `PUT /alarms/{lagoon_id}/thresholds/pt-fit`.
4. Backend crea/actualiza codigos:
   - `threshold_<tag>_min`
   - `threshold_<tag>_max`

Validaciones:

- `tag_id` inicia con `PT` o `FIT`.
- debe venir `min_value` o `max_value`.
- si ambos vienen, `min_value < max_value`.
- `severity` en `info|warning|critical`.

---

## 10) Verificacion rapida SQL

Ver layout asignado:

```sql
SELECT id, name, scada_layout, enable, product_type
FROM lagoons
ORDER BY id;
```

Ver mappings:

```sql
SELECT lagoon_id, layout_id, jsonb_object_keys(mapping_json) AS element_id, updated_at
FROM lagoon_layout_mapping
ORDER BY lagoon_id, layout_id, element_id;
```

Ver tags habilitados por collector:

```sql
SELECT lagoon_id, tag_id
FROM collector_tag_registry
ORDER BY lagoon_id, tag_id;
```

Ver historico disponible:

```sql
SELECT lagoon_id, tag_id, COUNT(*) AS rows_count, MAX(bucket) AS last_bucket
FROM scada_minute
GROUP BY lagoon_id, tag_id
ORDER BY lagoon_id, tag_id;
```
