# Flujo de Insercion y Publicacion SCADA

**Version doc:** 1.6.0
**Actualizado:** 2026-04-24

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

---

## 11) Alta de una nueva planta o laguna

En operacion muchas veces se habla de "planta", pero en codigo y base de datos el identificador canonico es `lagoon_id`.

Importante:

- hoy no existe un endpoint backend para crear una laguna desde cero;
- el alta base se hace por BD o por una herramienta administrativa externa;
- el mapping SCADA si puede mantenerse por API usando `layout-config`;
- si agregas o cambias `timezone` o insertas una laguna nueva con la app ya levantada, conviene reiniciar backend para precargar metadata en `RealtimeStateStore`.

### 11.1 Checklist previo

Antes de tocar BD define:

- `lagoon_id` unico y estable, en minusculas y con `_`, por ejemplo `costa_del_lago`.
- nombre visible de la planta/laguna.
- `product_type`: `crystal` o `small`.
- timezone IANA valida, por ejemplo `America/Santiago`.
- layout a reutilizar (`layout1`, `layout2`, etc.) o layout nuevo.
- inventario inicial de tags del collector.
- usuarios o roles que deben ver/editar/controlar la nueva planta.

### 11.2 Paso 1: crear el registro base en `lagoons`

Ejemplo SQL:

```sql
INSERT INTO lagoons (
  id,
  name,
  plc_type,
  timezone,
  ip,
  scada_layout,
  enable,
  product_type
)
VALUES (
  'costa_del_lago',
  'Costa del Lago',
  'S7-1200',
  'America/Santiago',
  '192.168.1.100',
  'layout1',
  TRUE,
  'crystal'
);
```

Validacion rapida:

```sql
SELECT id, name, product_type, timezone, scada_layout, enable
FROM lagoons
WHERE id = 'costa_del_lago';
```

### 11.3 Paso 2: reutilizar o crear el layout en `layouts`

Si la planta usa un layout existente, basta con referenciarlo desde `lagoons.scada_layout`.

Si necesitas uno nuevo, crea un registro en `layouts`. La clave aqui es que:

- `elements[].id` debe ser estable;
- las posiciones deben quedar en el layout, no en `mapping_json`;
- para overlays nuevos se recomienda `position: { "x": 0.45, "y": 0.32 }` con coordenadas relativas de `0..1`.

Ejemplo minimo:

```sql
INSERT INTO layouts (id, name, json_definition)
VALUES (
  'layout_costa',
  'Layout Costa',
  '{
    "svg_component": "layout1",
    "aspect_ratio": "1393.0437 / 1150",
    "elements": [
      {
        "id": "pressure_1",
        "type": "kpi",
        "default_label": "PT_117",
        "fallback_tag": "PT117_R_SCADA",
        "unit": "bar",
        "position": { "x": 0.45, "y": 0.32 }
      },
      {
        "id": "pump_status_1",
        "type": "pump",
        "default_label": "Bomba Principal",
        "svg_target": "pump_svg_id"
      }
    ]
  }'::jsonb
);
```

Validacion recomendada:

```sql
SELECT id, name, json_definition->>'svg_component' AS svg_component
FROM layouts
WHERE id = 'layout_costa';
```

### 11.4 Paso 3: crear el mapping por planta en `lagoon_layout_mapping`

La regla actual es:

- `layouts.json_definition` define estructura, posiciones y defaults;
- `lagoon_layout_mapping.mapping_json` define `tag`, `label` y opcionalmente `svg_target` por planta;
- las claves de `mapping_json` deben existir en `layout.json_definition.elements[].id`, o el backend devuelve `422`.

#### Opcion recomendada: via API

Si la laguna ya existe y el usuario tiene permiso de edicion:

```bash
curl -X PUT "http://localhost:8090/api/crystal/lagoons/costa_del_lago/layout-config" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "layout_id": "layout_costa",
    "mapping_json": {
      "pressure_1": {
        "tag": "PT117_R_SCADA",
        "label": "PT_117"
      },
      "pump_status_1": {
        "tag": "P006_STS_SCADA",
        "label": "Bomba Principal"
      }
    }
  }'
```

Ventajas de usar `PUT /api/{product}/lagoons/{lagoon_id}/layout-config`:

- valida claves desconocidas;
- actualiza `lagoons.scada_layout`;
- invalida cache de layout config;
- actualiza `state_store.set_lagoon_layout(...)` en runtime.

#### Opcion alternativa: via SQL

```sql
INSERT INTO lagoon_layout_mapping (lagoon_id, layout_id, mapping_json)
VALUES (
  'costa_del_lago',
  'layout_costa',
  '{
    "pressure_1": {
      "tag": "PT117_R_SCADA",
      "label": "PT_117"
    },
    "pump_status_1": {
      "tag": "P006_STS_SCADA",
      "label": "Bomba Principal"
    }
  }'::jsonb
);
```

Validacion:

```sql
SELECT lagoon_id, layout_id, updated_at
FROM lagoon_layout_mapping
WHERE lagoon_id = 'costa_del_lago';
```

### 11.5 Paso 4: registrar tags habilitados por collector

El backend consume `collector_tag_registry` para exponer `collector_tags` y el frontend lo usa para ocultar tarjetas cuyo tag no esta habilitado.

Ejemplo minimo:

```sql
INSERT INTO collector_tag_registry (lagoon_id, tag_id)
VALUES
  ('costa_del_lago', 'PT117_R_SCADA'),
  ('costa_del_lago', 'P006_STS_SCADA');
```

Nota:

- si tu tabla local tiene columnas adicionales como `enabled`, `created_at` o `collector_id`, completalas segun tu esquema;
- el backend actual solo lee `lagoon_id` y `tag_id`.

Validacion:

```sql
SELECT lagoon_id, tag_id
FROM collector_tag_registry
WHERE lagoon_id = 'costa_del_lago'
ORDER BY tag_id;
```

### 11.6 Paso 5: asignar permisos y visibilidad

La fuente de permisos por planta es `vw_user_lagoons`.

Eso significa que la asignacion real puede venir de tablas externas o del sistema de identidad, pero la verificacion operativa debe hacerse sobre la vista:

```sql
SELECT user_id, lagoon_id, can_view, can_edit, can_control
FROM vw_user_lagoons
WHERE lagoon_id = 'costa_del_lago'
ORDER BY user_id;
```

Reglas utiles:

- `AdminCrystal` y `AdminSmall` tienen alcance por producto;
- `VisualCrystal` y `VisualSmall` tienen lectura por producto;
- para permisos finos por planta se usa `can_view`, `can_edit`, `can_control`.

### 11.7 Paso 6: reiniciar backend si hubo alta o cambio directo en BD

Reinicio recomendado cuando:

- agregaste una laguna nueva en `lagoons`;
- cambiaste `timezone`;
- cambiaste `scada_layout` directo por SQL.

Motivo: en `lifespan` el backend precarga en `RealtimeStateStore`:

- timezone por laguna;
- layout actual por laguna;
- ultimo `pump_last_on`.

Si solo actualizaste el mapping via `PUT /layout-config`, el layout activo en runtime se refresca solo. Si cambiaste metadata base de la laguna, reiniciar sigue siendo la opcion segura.

### 11.8 Paso 7: probar ingest o collector

Smoke test de ingest:

```bash
curl -X POST "http://localhost:8090/ingest/scada" \
  -H "X-Api-Key: <COLLECTOR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "lagoon_id": "costa_del_lago",
    "timestamp": "2026-04-24T12:00:00Z",
    "tags": {
      "PT117_R_SCADA": 2.31,
      "P006_STS_SCADA": 1
    }
  }'
```

Resultado esperado:

- insercion en `scada_minute` y/o `scada_event`;
- actualizacion de `RealtimeStateStore`;
- `tick` por WebSocket;
- `current` y `last-minute` ya responden con datos.

### 11.9 Paso 8: validar REST, layout y WebSocket

Checklist recomendado:

1. La planta aparece en el listado correcto:

```bash
curl "http://localhost:8090/api/crystal/lagoons" \
  -H "Authorization: Bearer <TOKEN>"
```

2. El layout config responde:

```bash
curl "http://localhost:8090/api/crystal/lagoons/costa_del_lago/layout-config" \
  -H "Authorization: Bearer <TOKEN>"
```

3. Hay datos actuales:

```bash
curl "http://localhost:8090/api/crystal/lagoons/costa_del_lago/current" \
  -H "Authorization: Bearer <TOKEN>"
```

4. El frontend:

- muestra la planta en selector;
- renderiza SVG correcto;
- muestra KPIs esperados;
- no oculta tarjetas necesarias por falta de `collector_tags`.

5. WebSocket `/ws/scada/{lagoon_id}`:

- conecta sin `403`;
- entrega `lagoon_id`, `tags`, `plc_status`, `scada_layout`;
- si la timezone fue precargada correctamente, tambien entrega `local_time` y `timezone`.

### 11.10 Paso 9: alarmas y umbrales

Opcional pero recomendado despues del alta:

- configurar thresholds PT/FIT via `PUT /alarms/{lagoon_id}/thresholds/pt-fit`;
- verificar reglas `comm_loss` si la planta debe monitorearse por silencio de senal;
- revisar notificaciones por email si aplica.

### 11.11 Errores frecuentes

- La planta no aparece en frontend:
  revisar `lagoons.enable`, `product_type` y `vw_user_lagoons`.
- `PUT layout-config` devuelve `422`:
  alguna clave de `mapping_json` no existe en `layout.json_definition.elements[].id`.
- El mapa carga pero faltan tarjetas:
  revisar `collector_tag_registry`.
- Hay realtime pero no aparece `local_time`:
  probablemente falta reinicio despues de cargar `timezone`.
- La planta aparece pero usa layout incorrecto:
  revisar `lagoons.scada_layout` y el `layout_id` del ultimo `PUT /layout-config`.
