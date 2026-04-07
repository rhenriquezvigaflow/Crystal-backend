# Arquitectura End-to-End (Collector -> Backend)

**Version doc:** 1.0  
**Actualizado:** 2026-04-07  
**Audiencia:** desarrolladores nuevos (backend, integracion SCADA, soporte)

---

## 1) Objetivo de este documento

Explicar de punta a punta como funciona el sistema desde la captura de datos en PLC (collector) hasta el consumo por APIs/WebSocket en backend.

Incluye:

- repositorio y componentes
- flujo de datos en tiempo real
- catalogo de APIs y autenticacion
- modelo de datos principal
- flujo de alarmas
- puntos de extension para nuevos desarrollos

---

## 2) Repos y responsabilidades

### `collector_python`

Responsable de:

- conectarse a PLCs (Rockwell / Siemens)
- leer tags por ciclo (`poll_seconds`)
- normalizar tags y detectar eventos basicos
- enviar payloads por HTTP al backend (`POST /ingest/scada`)
- desacoplar lectura y envio con cola en memoria
- hacer spool local (`data/buffer.jsonl`) si falla backend

Archivos clave:

- `main.py`
- `workers/get_rockwell.py`
- `workers/get_siemens.py`
- `common/sender.py`
- `normalizer/tot_delta_normalizer.py`

### `crystal-backend`

Responsable de:

- autenticar ingest (API key)
- persistir historico/eventos SCADA
- mantener estado realtime en memoria por laguna
- emitir datos realtime por WebSocket
- exponer APIs REST (SCADA, producto, alarmas)
- evaluar motor de alarmas y notificaciones
- aplicar seguridad JWT + RBAC por laguna

Archivos clave:

- `app/main.py`
- `app/routers/ingest.py`
- `app/services/ingest_service.py`
- `app/state/store.py`
- `app/ws/routes.py`
- `app/scada/history/repo.py`
- `app/alarms/*`

---

## 3) Flujo end-to-end (resumen)

```text
PLC (Rockwell/Siemens)
   -> collector_python (read, normalize, queue)
   -> HTTP POST /ingest/scada (+ x-api-key)
   -> crystal-backend ingest router
   -> ingest_service (eventos + scada_minute)
   -> evaluate_alarms + notification jobs
   -> commit en PostgreSQL
   -> RealtimeStateStore update
   -> WebSocket broadcast (tick)
   -> Frontend consume REST + WS
```

---

## 4) Collector: como funciona internamente

## 4.1 Arranque

`main.py` carga configuracion YAML:

- modo single: 1 laguna por archivo
- modo master: `collectors.yml` con `plcs[].include`

Cada PLC corre en su propio hilo (ThreadPoolExecutor).

## 4.2 Ciclo de lectura

En cada ciclo:

1. `reader.read_once()` obtiene tags crudos.
2. Se normaliza `WM01_TOT_SCADA` a `WM01_TOT_DELTA_SCADA`.
3. Se detectan eventos:
   - booleanos (`OPEN/CLOSE`)
   - cambios de estado enteros (0,1,2,3)
4. Se construye payload con timestamp UTC.
5. Se encola para envio async.

## 4.3 Envio a backend

Un sender thread por laguna consume cola y hace `POST` al backend.

Header obligatorio:

- `X-Api-Key: <COLLECTOR_API_KEY>`

Si falla el envio:

- retry no bloqueante por ciclo siguiente
- opcional spool local JSONL (`runtime.spool_on_send_fail=true`)

## 4.4 Contrato de payload collector -> backend

```json
{
  "lagoon_id": "costa_del_lago",
  "timestamp": "2026-04-07T18:20:00+00:00",
  "tags": {
    "PT117_R_SCADA": 2.31,
    "FIT100_SCADA": 18.4
  }
}
```

Notas:

- `source` y `events` pueden existir en collector, pero backend opera sobre `lagoon_id`, `timestamp`, `tags`.
- si `timestamp` no viene, backend usa `now()` en UTC.

---

## 5) Backend: startup y runtime

`app/main.py` en `lifespan`:

1. crea singletons:
   - `RealtimeStateStore`
   - `WebSocketManager`
2. carga timezone de lagunas desde tabla `lagoons`
3. precarga `pump_last_on` desde historico
4. inicia:
   - `ScadaStallWatchdog`
   - `AlarmLagoonSignalMonitor`

En shutdown, detiene monitor y watchdog.

---

## 6) Backend ingest pipeline

Endpoint:

- `POST /ingest/scada`

Archivo:

- `app/routers/ingest.py`

Flujo:

1. valida `x-api-key` (`verify_collector_key`).
2. parsea body (`lagoon_id`, `timestamp?`, `tags`).
3. ejecuta persistencia en thread con timeout (`INGEST_TIMEOUT_SEC`).
4. `_persist_ingest()` hace:
   - `ingest_service.ingest(...)` para `scada_event`/`scada_minute`
   - `evaluate_alarms(...)` para motor de alarmas
   - `dispatch_notifications(...)` (post-commit)
5. actualiza `RealtimeStateStore`.
6. emite `tick` por WS a la laguna.
7. responde `{"ok": true}`.

Errores relevantes:

- `401` API key invalida
- `504` timeout de ingest
- `500` error interno

---

## 7) APIs REST (catalogo funcional)

## 7.1 Publicas

- `GET /health`
- `POST /auth/login`

## 7.2 SCADA general (JWT + rol lectura + permiso laguna)

- `GET /scada/{lagoon_id}/last-minute`
- `GET /scada/{lagoon_id}/current`
- `GET /scada/{lagoon_id}/pump-events/last-3`
- `GET /scada/history/{resolution}` (`hourly|daily|weekly`)

## 7.3 RBAC por laguna

- `GET /lagoons` (`can_view`)
- `PUT /lagoons/{id}` (`can_edit`)
- `POST /control/pump` (`can_control`)

## 7.4 APIs de producto

Crystal:

- `/api/crystal/lagoons`
- `/api/crystal/dashboard`
- `/api/crystal/lagoons/{lagoon_id}/last-minute`
- `/api/crystal/lagoons/{lagoon_id}/current`
- `/api/crystal/lagoons/{lagoon_id}/pump-events/last-3`
- `/api/crystal/history`
- `/api/crystal/layout` (`GET|PUT|DELETE`)
- `/api/crystal/tags` (`GET|PUT|DELETE`)

Small:

- `/api/small/lagoons`
- `/api/small/dashboard`
- `/api/small/lagoons/{lagoon_id}/last-minute`
- `/api/small/lagoons/{lagoon_id}/current`
- `/api/small/lagoons/{lagoon_id}/pump-events/last-3`
- `/api/small/history`
- `/api/small/control` (`POST|PUT`)
- `/api/small/chemicals` (`GET|POST|DELETE`)

## 7.5 Alarmas PT/FIT (contrato actual)

Lectura consolidada:

- `GET /alarms/{lagoon_id}/thresholds/pt-fit/view`

Escritura:

- `PUT /alarms/{lagoon_id}/thresholds/pt-fit`

Aliases soportados por router:

- `/crystal/alarms/...`
- `/small/alarms/...`
- `/api/alarms/...`
- `/api/crystal/alarms/...`
- `/api/small/alarms/...`

---

## 8) WebSocket realtime

Endpoints activos:

- `WS /ws/scada?lagoon_id=<id>&token=<jwt>`
- `WS /ws/scada/{lagoon_id}?token=<jwt>`
- `WS /ws/crystal/{lagoon_id}?token=<jwt>`
- `WS /ws/small/{lagoon_id}?token=<jwt>`

Handshake:

1. valida token JWT (query `token` o header `Authorization`).
2. valida permiso `can_view` sobre `lagoon_id`.
3. envia `snapshot` inicial.
4. luego envia `tick` en cada ingest de esa laguna.

Campos relevantes del payload:

- `plc_status` (`online|offline`)
- `local_time`, `timezone`
- `tags`
- `pump_last_on`

---

## 9) Seguridad (modelo actual)

## 9.1 Ingest

- Protegido con API key (`x-api-key`).
- Valor esperado en backend: `settings.COLLECTOR_API_KEY`.

## 9.2 API usuario

- Login por `POST /auth/login`.
- Token bearer para endpoints protegidos.

Roles usados:

- `AdminCrystal`, `VisualCrystal`, `AdminSmall`, `VisualSmall`

Permisos por laguna (vista `vw_user_lagoons`):

- `can_view`
- `can_edit`
- `can_control`

---

## 10) Modelo de datos (tablas/vistas clave)

Tablas:

- `lagoons` (catalogo, timezone, layout, product_type)
- `scada_event` (transiciones de estado por tag)
- `scada_minute` (agregado por minuto)
- `alarm_definition` (reglas)
- `alarm_event` (OPEN/CLOSE)
- `alarm_notification_rule` (routing)
- `users`, `roles`, `user_roles`

Vistas/objetos consultados:

- `vw_user_lagoons` (RBAC por laguna)
- `vw_scada_last_3_pump_actions` (ultimos eventos de bomba)
- `scada_minute_hourly`, `scada_minute_daily`, `scada_minute_weekly` (si existen)
- `vw_alarm_thresholds_pt_fit_lagoon` (base de lectura consolidada de umbrales)

---

## 11) Alarmas (state, comm_loss, threshold)

Motor:

- evaluacion en cada ingest (`evaluate_alarms`)
- monitor por reloj para perdida de senal de laguna (`AlarmLagoonSignalMonitor`)

Tipos:

- `state`: por transiciones de estado
- `comm_loss`: timeout por tag o por laguna
- `threshold`: limites PT/FIT min/max

Notificaciones:

- se generan en transicion `OPEN`
- se enrutan por `alarm_notification_rule`
- se despachan luego del commit

---

## 12) Historial y estrategia de rendimiento

`GET /scada/history/{resolution}` usa:

1. vista continua (`source=view`) si existe
2. fallback `time_bucket` sobre `scada_minute` (`source=table`) si no existe

Para umbrales PT/FIT:

- frontend lee un solo endpoint consolidado (`/view`)
- se evita merge de endpoints legacy en cliente

---

## 13) Variables de entorno minimas

Collector (`collector_python/.env`):

- `COLLECTOR_API_KEY`

Backend (`crystal-backend/.env`):

- `DATABASE_URL`
- `COLLECTOR_API_KEY`
- `JWT_SECRET_KEY`

Comunes recomendadas:

- `INGEST_TIMEOUT_SEC`
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`
- flags de monitor/watchdog/alarms segun entorno

---

## 14) Troubleshooting rapido

## 14.1 Collector envia pero backend responde 401

- validar que `COLLECTOR_API_KEY` coincide en ambos lados.

## 14.2 Frontend no recibe WS

- validar JWT y permiso `can_view`.
- validar URL WS real usada por frontend (`/ws/scada/{lagoon_id}?token=...`).

## 14.3 History lento

- confirmar existencia de vistas continuas.
- revisar rango de fechas y cantidad de tags solicitados.

## 14.4 Umbrales PT/FIT no aparecen

- confirmar telemetria PT/FIT en `scada_minute`/`scada_event`.
- validar permiso `can_view` sobre laguna.
- verificar que endpoint usado sea `/thresholds/pt-fit/view`.

---

## 15) Donde tocar codigo segun necesidad

Cambiar logica de lectura PLC:

- `collector_python/workers/*`

Cambiar contrato ingest:

- `app/routers/ingest.py`
- `app/services/ingest_service.py`
- `app/schemas/*`

Cambiar reglas de alarmas:

- `app/alarms/service.py`
- `app/alarms/thresholds/*`

Cambiar RBAC/seguridad:

- `app/security/*`
- `app/auth/services/lagoon_service.py`

Cambiar payload WS:

- `app/state/store.py`
- `app/ws/routes.py`
- `app/ws/manager.py`

---

## 16) Referencias recomendadas

- `docs/INDEX.md`
- `docs/ARQUITECTURA_Y_FLUJO.md`
- `docs/FLUJO_INSERCION.md`
- `docs/README_ALARM_THRESHOLDS_API.md`
- `../collector_python/ARQUITECTURA.md`
- `../collector_python/DOCUMENTACION_TECNICA.md`

