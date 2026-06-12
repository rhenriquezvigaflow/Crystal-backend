# Arquitectura y Flujo - Crystal Lagoons Backend

**Ultima actualizacion:** 2026-06-12  
**Version:** 2.0.0

## Vision General

El backend es una API FastAPI para telemetria SCADA, alarmas, historico y acceso por RBAC.

```text
Collector -> /ingest/scada -> IngestService -> PostgreSQL
                                |
                                +-> Alarm engine
                                +-> RealtimeStateStore -> WebSocketManager

Frontend -> REST /api/* -> /auth, /{product}, /scada, /alarms
Frontend -> WS /ws/{product_type}/{lagoon_id}
Frontend -> escenas locales src/assets/positions/*.json
```

## Startup y Ciclo de Vida

`app/main.py` registra routers e inicializa durante `lifespan`:

1. `RealtimeStateStore`.
2. `WebSocketManager`.
3. Timezones desde `lagoons`.
4. Precarga de `pump_last_on` desde `scada_event`.
5. `ScadaStallWatchdog`.
6. `AlarmLagoonSignalMonitor`.

En shutdown detiene monitores.

## Routers Registrados

- `app.routers.health`
- `app.auth.auth`
- `app.auth.routers.lagoons_router`
- `app.routers.ingest`
- `app.routers.alarm_thresholds`
- `app.routers.email`
- `app.routers.websocket`
- `app.routers.scada`
- `app.routers.events`
- `app.modules.crystal.router`
- `app.modules.small.router`
- `app.routers.small.control`
- `app.routers.small.chemicals`

## Seguridad

### Ingest

`POST /ingest/scada` exige:

- `X-Api-Key: <COLLECTOR_API_KEY>`

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

La fuente de permisos finos es `vw_user_lagoons`.

## Componentes Principales

- `app/main.py`: bootstrap, routers, lifecycle.
- `app/routers/ingest.py`: ingest SCADA.
- `app/services/ingest_service.py`: eventos y `scada_minute`.
- `app/state/store.py`: estado realtime por laguna.
- `app/routers/websocket.py`: WebSocket SCADA.
- `app/routers/scada.py`: realtime HTTP, historico y KPIs.
- `app/routers/events.py`: eventos, eventos de bombas y XLSX.
- `app/modules/shared/product_router.py`: router generico por producto.
- `app/modules/crystal/router.py`: endpoints Crystal productizados.
- `app/modules/small/router.py`: endpoints Small productizados.
- `app/auth/services/lagoon_service.py`: alcance por producto y permisos.
- `app/alarms/*`: motor de alarmas.
- `app/alarms/thresholds/*`: API de umbrales PT/FIT.

## Endpoints Activos

Salud:

- `GET /health`
- `GET /health/live`
- `GET /health/ready`

Auth/RBAC:

- `POST /auth/login`
- `GET /lagoons`
- `PUT /lagoons/{id}`
- `POST /control/pump`

Ingest:

- `POST /ingest/scada`

`product_type` es opcional en el payload. Cuando viene, debe coincidir con `lagoons.product_type`; esto protege las rutas Crystal/Small de datos cruzados.

SCADA:

- `GET /scada/{lagoon_id}/realtime`
- `GET /scada/{lagoon_id}/history`
- `GET /scada/{lagoon_id}/kpis`
- `GET /scada/{lagoon_id}/events`
- `GET /scada/{lagoon_id}/pump-events`
- `GET /scada/{lagoon_id}/pump-events/last-3`
- `GET /scada/{lagoon_id}/pump-events/report.xlsx`

Alarmas/email:

- `GET /alarms/{lagoon_id}/thresholds/pt-fit/view`
- `PUT /alarms/{lagoon_id}/thresholds/pt-fit`
- `POST /email/test-alert`

Small:

- `GET /small/lagoons`
- `GET /small/dashboard`
- `GET /small/lagoons/{lagoon_id}/last-minute`
- `GET /small/lagoons/{lagoon_id}/current`
- `GET /small/history`
- `GET /small/lagoons/{lagoon_id}/pump-events/last-3`
- `GET /small/lagoons/{lagoon_id}/pump-events/report.xlsx`
- `POST /small/tags/write`
- `POST /small/control`
- `PUT /small/control`
- `GET /small/chemicals`
- `POST /small/chemicals`
- `DELETE /small/chemicals`

Crystal productizado:

- `GET /crystal/lagoons`
- `GET /crystal/dashboard`
- `GET /crystal/lagoons/{lagoon_id}/last-minute`
- `GET /crystal/lagoons/{lagoon_id}/current`
- `GET /crystal/history`
- `GET /crystal/lagoons/{lagoon_id}/pump-events/last-3`
- `GET /crystal/lagoons/{lagoon_id}/pump-events/report.xlsx`

WebSocket:

- `WS /ws/scada/{lagoon_id}`
- `WS /ws/{product_type}/{lagoon_id}`

## Historico

Implementacion: `app/scada/history/repo.py`.

Reglas:

1. Resolucion: `hourly|daily|weekly`.
2. Si `end_date < start_date`, se invierte rango.
3. Usa vista continua si existe.
4. Si no, fallback sobre `scada_minute`.
5. Respuesta: `series[{tag, points}]`.

## WebSocket

Endpoint:

- `WS /ws/scada/{lagoon_id}`
- `WS /ws/{product_type}/{lagoon_id}` para clientes productizados

Payload relevante:

- `type`
- `lagoon_id`
- `ts`
- `plc_status`
- `local_time`
- `timezone`
- `tags`
- `pump_last_on`
- `start_ts`

## Layout Visual

El backend actual no registra endpoints de layout o mapping. La UI visual se configura en:

- `crystal-frontend/src/assets/positions/*.json`
- `crystal-frontend/src/scada/svgRegistry.ts`

El backend entrega datos y permisos; el frontend decide posiciones, labels y `svg_target`.

## Modelos y Vistas de Datos

Tablas:

- `lagoons`
- `scada_event`
- `scada_minute`
- `alarm_definition`
- `alarm_event`
- `alarm_notification_rule`
- `users`, `roles`, `user_roles`

Vistas/objetos externos:

- `vw_user_lagoons`
- `vw_scada_last_3_pump_actions`
- `scada_minute_hourly`, `scada_minute_daily`, `scada_minute_weekly`
- `vw_alarm_thresholds_pt_fit_lagoon`
- `sp_sync_collector_tags_and_alarms`, opcional

## Referencias Cruzadas

- [ONE_PAGE_SUMMARY.md](./ONE_PAGE_SUMMARY.md)
- [FLUJO_INSERCION.md](./FLUJO_INSERCION.md)
- [SMALL_LAGOONS.md](./SMALL_LAGOONS.md)
- [GUIA_TECNICA_DESARROLLO.md](./GUIA_TECNICA_DESARROLLO.md)
- [README_ALARM_THRESHOLDS_API.md](./README_ALARM_THRESHOLDS_API.md)
