# Arquitectura y Flujo - Crystal Lagoons Backend

**Ultima actualizacion:** 2026-04-09
**Version:** 1.4.0

---

## Vision general

El backend es una API FastAPI para telemetria SCADA, alarmas, historico, layouts dinamicos y acceso por RBAC.

```text
Collector -> /ingest/scada -> IngestService -> PostgreSQL
                                |
                                +-> Alarm engine
                                +-> RealtimeStateStore -> WebSocketManager

Frontend -> REST /api/* + /layouts/* + /lagoons/*/mapping
Frontend -> WS /ws/scada/{lagoon_id}
```

---

## Startup y ciclo de vida

`app/main.py` registra routers e inicializa durante `lifespan`:

1. `RealtimeStateStore`.
2. `WebSocketManager`.
3. Timezones y `scada_layout` desde `lagoons`.
4. Precarga de `pump_last_on` desde `vw_scada_last_3_pump_actions`.
5. `ScadaStallWatchdog`.
6. `AlarmLagoonSignalMonitor`.

En shutdown detiene monitores.

---

## Seguridad

### Ingest

`POST /ingest/scada` exige:

- `x-api-key: <COLLECTOR_API_KEY>`

### JWT y RBAC

`POST /auth/login` entrega JWT. Claims esperadas:

- `sub`
- `email`
- `roles`
- `role` legacy

Roles:

- `AdminCrystal`
- `VisualCrystal`
- `AdminSmall`
- `VisualSmall`
- `SuperAdmin`

Permisos por laguna:

- `can_view`
- `can_edit`
- `can_control`

La fuente de permisos es `vw_user_lagoons`.

---

## Componentes principales

- `app/main.py`: bootstrap, routers, lifecycle.
- `app/routers/ingest.py`: ingest SCADA.
- `app/services/ingest_service.py`: eventos y `scada_minute`.
- `app/state/store.py`: estado realtime por laguna.
- `app/ws/routes.py`: WebSocket SCADA.
- `app/scada/history/repo.py`: historico con vista o fallback.
- `app/layout_config/*`: servicio, repositorio y schemas de layout dinamico.
- `app/routers/scada_layouts.py`: endpoints `/layouts` y `/lagoons/{id}/mapping`.
- `app/alarms/*`: motor de alarmas.
- `app/alarms/thresholds/*`: API de umbrales PT/FIT.

---

## Layout SCADA dinamico

La arquitectura separa:

1. SVG visual estatico.
2. Definicion del layout (`layouts.json_definition`).
3. Mapping por laguna (`lagoon_layout_mapping.mapping_json`).
4. Datos realtime (`tags` por WebSocket).

### Tabla `layouts`

Campos principales:

- `id`
- `name`
- `json_definition`
- `created_at`
- `updated_at`

`json_definition.elements[]` puede contener:

```json
{
  "id": "pressure_1",
  "type": "kpi",
  "fallback_tag": "PT117_R_SCADA",
  "unit": "bar",
  "default_label": "PT117_R_SCADA",
  "position": { "left": "21.3%", "top": "40.3%" }
}
```

Tipos usados por frontend:

- `kpi`
- `pump`
- `valve`
- `plc_status`

Campos frecuentes:

- `position`
- `fallback_tag`
- `default_label`
- `unit`
- `icon_type`
- `panel`
- `svg_target`
- `always_visible`

### Tabla `lagoon_layout_mapping`

Campos principales:

- `id`
- `lagoon_id`
- `layout_id`
- `mapping_json`
- `created_at`
- `updated_at`

Restriccion:

- unico por `(lagoon_id, layout_id)`.

`mapping_json`:

```json
{
  "pressure_1": {
    "tag": "PT117_R_SCADA",
    "label": "PT_117"
  },
  "pump_retorno_clarificado": {
    "tag": "P007_STS_SCADA",
    "label": "Bomba Retorno Clarificado",
    "svg_target": "BOMBA-RETORNO-CLARIFICADO"
  }
}
```

### Validacion

- Las claves del mapping deben existir en `layout.json_definition.elements[].id`.
- En `GET`, claves desconocidas vuelven como `warnings`.
- En `PUT`, claves desconocidas generan `422`.

### Cache

- Layouts y mappings se cachean en memoria.
- TTL: `SCADA_LAYOUT_CACHE_TTL_SEC` o `LAYOUT_CONFIG_CACHE_TTL_SEC`.
- `PUT` invalida cache de la laguna.
- `collector_tags` se refresca aunque haya mapping cacheado.

### Collector tags

`collector_tag_registry` entrega los tags habilitados por collector para la laguna. El frontend usa ese arreglo para ocultar tarjetas cuyo tag no existe o no esta habilitado.

---

## Endpoints de layout

Generales:

- `GET /layouts/{layout_id}`
- `GET /api/layouts/{layout_id}`
- `GET /lagoons/{lagoon_id}/mapping`
- `GET /api/lagoons/{lagoon_id}/mapping`
- `PUT /lagoons/{lagoon_id}/mapping`
- `PUT /api/lagoons/{lagoon_id}/mapping`

Producto:

- `GET /api/crystal/lagoons/{lagoon_id}/layout-config`
- `PUT /api/crystal/lagoons/{lagoon_id}/layout-config`
- `GET /api/small/lagoons/{lagoon_id}/layout-config`
- `PUT /api/small/lagoons/{lagoon_id}/layout-config`

`layout-config` responde:

```json
{
  "lagoon_id": "costa_del_lago",
  "layout": {
    "id": "layout2",
    "name": "Crystal Layout 2",
    "json_definition": { "elements": [] }
  },
  "mapping": {
    "lagoon_id": "costa_del_lago",
    "layout_id": "layout2",
    "mapping_json": {},
    "collector_tags": ["PT112_R_SCADA"],
    "warnings": [],
    "updated_at": "2026-04-09T20:00:00Z"
  }
}
```

---

## Historico

Implementacion: `app/scada/history/repo.py`.

Reglas:

1. Resolucion: `hourly|daily|weekly`.
2. Si `end_date < start_date`, se invierte rango.
3. Usa vista continua si existe.
4. Si no, fallback con `time_bucket` sobre `scada_minute`.
5. Respuesta de APIs de producto: `series[{tag, points}]`.

---

## WebSocket

Endpoints:

- `WS /ws/scada?lagoon_id=<id>&token=<jwt>`
- `WS /ws/scada/{lagoon_id}?token=<jwt>`
- `WS /ws/crystal/{lagoon_id}?token=<jwt>`
- `WS /ws/small/{lagoon_id}?token=<jwt>`

Payload relevante:

- `type`
- `lagoon_id`
- `ts`
- `plc_status`
- `local_time`
- `timezone`
- `scada_layout`
- `tags`
- `pump_last_on`
- `start_ts`

---

## Modelos y vistas de datos

Tablas:

- `lagoons`
- `layouts`
- `lagoon_layout_mapping`
- `collector_tag_registry`
- `scada_event`
- `scada_minute`
- `alarm_definition`
- `alarm_event`
- `alarm_notification_rule`
- `users`, `roles`, `user_roles`

Vistas:

- `vw_user_lagoons`
- `vw_scada_last_3_pump_actions`
- `scada_minute_hourly`, `scada_minute_daily`, `scada_minute_weekly`
- `vw_alarm_thresholds_pt_fit_lagoon`

---

## Referencias cruzadas

- [ONE_PAGE_SUMMARY.md](./ONE_PAGE_SUMMARY.md)
- [FLUJO_INSERCION.md](./FLUJO_INSERCION.md)
- [GUIA_TECNICA_DESARROLLO.md](./GUIA_TECNICA_DESARROLLO.md)
- [README_ALARM_THRESHOLDS_API.md](./README_ALARM_THRESHOLDS_API.md)
