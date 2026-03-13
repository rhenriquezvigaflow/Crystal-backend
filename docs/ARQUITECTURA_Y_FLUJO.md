# Arquitectura y Flujo - Crystal Lagoons Backend

**Ultima actualizacion:** 2026-03-13
**Version:** 1.2

---

## Tabla de contenidos

1. Vision general
2. Startup y ciclo de vida
3. Seguridad
4. Componentes principales
5. Endpoints activos
6. Flujos funcionales
7. Modelos y vistas de datos
8. Configuracion operativa

---

## Vision general

El backend es una API FastAPI que:

- ingiere datos SCADA en tiempo real,
- persiste historico y eventos de estado,
- mantiene estado en memoria por laguna,
- publica snapshot/tick por websocket,
- aplica control de acceso por JWT + RBAC.

Arquitectura logica:

```text
Collector -> /ingest/scada -> IngestService -> PostgreSQL
                                |
                                +-> RealtimeStateStore -> WebSocketManager

User UI -> /auth/login -> JWT
User UI -> /scada/*, /api/* (bearer token)
User UI -> /ws/* (token + permiso por laguna)
```

---

## Startup y ciclo de vida

`app/main.py` define `lifespan` y durante startup ejecuta:

1. Crea singletons:
   - `app.state.state_store` (`RealtimeStateStore`)
   - `app.state.ws_manager` (`WebSocketManager`)
2. Carga `timezone` por laguna desde tabla `lagoons`.
3. Detecta lagunas con eventos y precarga `pump_last_on` desde `vw_scada_last_3_pump_actions`.
4. Inicia `ScadaStallWatchdog`.

En shutdown detiene watchdog.

---

## Seguridad

### 1) Ingest por API key

`POST /ingest/scada` exige header:

- `x-api-key: <COLLECTOR_API_KEY>`

Validado por `app/security/api_key.py`.

### 2) Login y JWT

`POST /auth/login` retorna:

- `access_token`
- `token_type` (`bearer`)
- `expires_in`
- `user` con `roles` y `role` (compatibilidad legacy)

Claims esperadas en token:

- `sub` (user_id)
- `email`
- `roles` (lista)
- `role` (string legacy)

### 3) Roles

Roles vigentes:

- `AdminCrystal`
- `VisualCrystal`
- `AdminSmall`
- `VisualSmall`

Grupos usados por dependencias RBAC:

- Crystal read: `AdminCrystal`, `VisualCrystal`
- Crystal write: `AdminCrystal`
- Small read: `AdminSmall`, `VisualSmall`
- Small write: `AdminSmall`
- Read general SCADA: union de todos los de lectura

### 4) Permisos por laguna

Permisos evaluados sobre `vw_user_lagoons`:

- `can_view`
- `can_edit`
- `can_control`

Dependencias:

- `require_permission(...)` para HTTP
- `ensure_websocket_permission(...)` para WebSocket

### 5) WebSocket auth

Soporta token por:

- query `token=<jwt>`
- header `Authorization: Bearer <jwt>`

Si no hay token, token invalido o permiso insuficiente -> cierre WS con policy violation (`1008`).

---

## Componentes principales

### FastAPI app (`app/main.py`)

Responsable de:

- registrar routers,
- inicializar estado y watchdog,
- configurar CORS.

### Ingest router (`app/routers/ingest.py`)

- endpoint: `POST /ingest/scada`
- parsea payload `{lagoon_id, timestamp?, tags}`
- persiste en hilo separado con timeout configurable (`INGEST_TIMEOUT_SEC`)
- actualiza estado y hace broadcast WS

### Ingest service (`app/services/ingest_service.py`)

- detecta cambios de estado (`_last_state`)
- cierra evento abierto y crea nuevo evento de `STATE_CHANGE`
- mantiene buffer por minuto
- hace upsert por lote en `scada_minute`

### RealtimeStateStore (`app/state/store.py`)

Mantiene por laguna:

- tags actuales
- ultimo timestamp (`ts`)
- `pump_last_on`
- `start_ts`
- timezone

Normaliza tags de valvulas de layout 2 (`ve237`, `ve238`, etc.) y calcula:

- `plc_status` (`online`/`offline`)
- `local_time`

### WebSocketManager (`app/ws/manager.py`)

- mantiene conexiones por `lagoon_id`
- envia `snapshot` al conectar
- envia `tick` en cada ingest

### Historial (`app/scada/history/repo.py`)

- selecciona resolucion (`hourly`, `daily`, `weekly`)
- usa vista continua si existe (`source=view`)
- fallback con `time_bucket` sobre `scada_minute` (`source=table`)

---

## Endpoints activos

### Publicos

- `GET /health`
- `POST /auth/login`

### Ingest

- `POST /ingest/scada` (x-api-key)

Body:

```json
{
  "lagoon_id": "costa_del_lago",
  "timestamp": "2026-03-13T14:30:45Z",
  "tags": {
    "bomba_1": 1,
    "temperatura": 28.5
  }
}
```

### SCADA general (bearer + rol lectura)

- `GET /scada/{lagoon_id}/last-minute`
- `GET /scada/{lagoon_id}/current`
- `GET /scada/{lagoon_id}/pump-events/last-3`
- `GET /scada/history/{resolution}`

`resolution` en path: `hourly|daily|weekly`.

### RBAC por permisos

- `GET /lagoons` -> requiere `can_view` (cualquier laguna)
- `PUT /lagoons/{id}` -> requiere `can_edit` sobre `{id}`
- `POST /control/pump` -> valida `can_control` sobre `cmd.lagoon_id`

### APIs Crystal

- `GET /api/crystal/lagoons`
- `GET /api/crystal/dashboard`
- `GET /api/crystal/lagoons/{lagoon_id}/last-minute`
- `GET /api/crystal/lagoons/{lagoon_id}/current`
- `GET /api/crystal/lagoons/{lagoon_id}/pump-events/last-3`
- `GET /api/crystal/history`
- `GET /api/crystal/layout`
- `PUT /api/crystal/layout`
- `DELETE /api/crystal/layout`
- `GET /api/crystal/tags`
- `PUT /api/crystal/tags`
- `DELETE /api/crystal/tags`

### APIs Small

- `GET /api/small/lagoons`
- `GET /api/small/dashboard`
- `GET /api/small/lagoons/{lagoon_id}/last-minute`
- `GET /api/small/lagoons/{lagoon_id}/current`
- `GET /api/small/lagoons/{lagoon_id}/pump-events/last-3`
- `GET /api/small/history`
- `POST /api/small/control`
- `PUT /api/small/control`
- `GET /api/small/chemicals`
- `POST /api/small/chemicals`
- `DELETE /api/small/chemicals`

### WebSocket

- `WS /ws/scada?lagoon_id=<id>&token=<jwt>`
- `WS /ws/scada/{lagoon_id}?token=<jwt>`
- `WS /ws/crystal/{lagoon_id}?token=<jwt>`
- `WS /ws/small/{lagoon_id}?token=<jwt>`

---

## Flujos funcionales

### Flujo de ingest

1. Collector llama `POST /ingest/scada` con `x-api-key`.
2. Router valida payload y define timestamp UTC.
3. Router ejecuta `_persist_ingest(...)` en thread.
4. `ingest_service.ingest(...)`:
   - detecta cambios de estado,
   - cierra/abre eventos en `scada_event`,
   - flushea minutos cerrados en `scada_minute`.
5. Router actualiza `RealtimeStateStore`.
6. Router hace `ws_manager.broadcast(...)` con `tick_payload`.

### Flujo de lectura REST

- `last-minute`: ultimo bucket de `scada_minute`.
- `current`: ultimo valor por tag para laguna.
- `history`: vista continua o fallback, agrupa en `series`.
- `pump-events/last-3`: lee `vw_scada_last_3_pump_actions`.

### Flujo websocket

1. Cliente abre WS con token y lagoon.
2. Se valida permiso `can_view` para lagoon.
3. Servidor envia `snapshot` inicial.
4. En cada ingest se envia `tick` a conexiones de esa laguna.

---

## Modelos y vistas de datos

### Tablas principales

- `lagoons`
  - `id`, `name`, `plc_type`, `timezone`, `ip`, `scada_layout`, `product_type`
- `scada_event`
  - `id`, `lagoon_id`, `tag_id`, `state`, `previous_state`, `start_ts`, `end_ts`, `duration_sec`
- `scada_minute`
  - `id`, `lagoon_id`, `tag_id`, `bucket`, `state`, `value_num`, `value_bool`
- `users`, `roles`, `user_roles`

### Vistas y objetos usados por consultas

- `vw_scada_last_3_pump_actions`
- `vw_user_lagoons`
- `public.scada_minute_hourly`
- `public.scada_minute_daily`
- `public.scada_minute_weekly`

Scripts relevantes:

- `scripts/sql/create_rbac_tables.sql`
- `scripts/seed_roles.py`
- `scripts/sql/create_scada_continuous_aggregates.sql`

---

## Configuracion operativa

Variables requeridas:

- `DATABASE_URL`
- `COLLECTOR_API_KEY`
- `JWT_SECRET_KEY`

Variables comunes:

- `JWT_ALGORITHM`
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`
- `INGEST_TIMEOUT_SEC`
- `SCADA_WATCHDOG_*`

CORS permitidos por defecto:

- `http://192.168.1.22`
- `http://localhost:5173`
- `http://localhost:3000`
- `http://localhost:5174`
- `http://localhost:8080`

---

## Referencias cruzadas

- [FLUJO_INSERCION.md](./FLUJO_INSERCION.md)
- [GUIA_TECNICA_DESARROLLO.md](./GUIA_TECNICA_DESARROLLO.md)
- [DIAGRAMAS_FLUJOS.md](./DIAGRAMAS_FLUJOS.md)
- [CHANGELOG.md](./CHANGELOG.md)
