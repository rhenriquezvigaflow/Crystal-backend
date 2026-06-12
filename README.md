# Crystal Lagoons - SCADA Backend

Backend FastAPI para ingesta SCADA, lectura realtime, historico, eventos, RBAC y motor de alarmas.

## Alcance Actual

- `POST /ingest/scada` protegido con `X-Api-Key`.
- Estado realtime en memoria + broadcast WebSocket.
- Persistencia de `scada_minute` y `scada_event`.
- Consultas SCADA (`realtime`, `history`, `kpis`, `events`, `pump-events`).
- RBAC por laguna para lectura, edicion y control.
- Catalogo de lagunas desde tabla `lagoons`.
- Rutas por producto para Crystal y Small (`/crystal/*`, `/small/*`).
- Alarmas `state`, `comm_loss` y `threshold`.
- Umbrales PT/FIT configurables.
- Notificaciones por email reales via SMTP y webhook simulado por log.
- Validacion opcional de `product_type` durante ingest para evitar mezclar payloads Crystal y Small.

Nota importante: el backend actual no registra endpoints de layouts/mapping SCADA. La UI visual carga escenas locales desde `crystal-frontend/src/assets/positions/*.json`.

## Integracion con Frontend y Collector

```text
collector_python
  -> POST /ingest/scada
  -> sync collector tags/alarms si existe la funcion SQL
  -> persist scada_minute / scada_event
  -> evaluate_alarms()
  -> dispatch_notifications()
  -> state_store + ws_manager
  -> crystal-frontend
```

## Prefijo `/api`

El backend define rutas sin prefijo en codigo (`/health`, `/scada/...`, `/alarms/...`), pero la app corre con `root_path="/api"` para despliegues detras de proxy.

En practica:

- backend directo local: `/health`, `/scada/...`
- frontend o proxy IIS/Vite: `/api/health`, `/api/scada/...`

Las rutas listadas abajo son las rutas directas de FastAPI. En despliegue detras de proxy/root path, el browser las consume bajo `/api`.

## Puesta en Marcha

### 1. Instalar dependencias

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Variables minimas

`.env` debe incluir al menos:

```env
DATABASE_URL=postgresql://user:pass@host:5432/dbname
COLLECTOR_API_KEY=tu-clave-segura-del-collector
JWT_SECRET_KEY=una-clave-larga-y-segura
LOG_LEVEL=INFO
```

Para email:

```env
MAIL_USERNAME=...
MAIL_PASSWORD=...
MAIL_FROM=...
MAIL_SERVER=smtp-mail.outlook.com
MAIL_PORT=587
MAIL_STARTTLS=true
MAIL_SSL_TLS=false
MAIL_FROM_NAME=Crystal SCADA
MAIL_TIMEOUT_SEC=15
MAIL_DISPATCH_MAX_WORKERS=2
```

### 3. Ejecutar

```powershell
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8090
```

Alternativa:

```powershell
run_backend.bat
```

## Modulos Principales

- `app/main.py`: bootstrap, CORS, lifespan, watchdog y signal monitor.
- `app/routers/ingest.py`: entrada de telemetria del collector.
- `app/services/ingest_service.py`: minute buffers y eventos SCADA.
- `app/routers/scada.py`: realtime HTTP, historico y KPIs.
- `app/routers/events.py`: eventos y reportes XLSX.
- `app/routers/websocket.py`: WebSocket autenticado por laguna.
- `app/auth/auth.py`: login JWT.
- `app/auth/routers/lagoons_router.py`: lagunas y permisos RBAC.
- `app/modules/shared/product_router.py`: endpoints productizados para lagunas, current, last-minute, historico y eventos.
- `app/modules/crystal/router.py`: router Crystal.
- `app/modules/small/router.py`: router Small Lagoons.
- `app/alarms/service.py`: evaluacion y transiciones OPEN/CLOSE.
- `app/alarms/thresholds/*`: umbrales PT/FIT.
- `app/integration/notifications.py`: orquestador de canales.
- `app/services/email_service.py`: render de plantilla y envio SMTP.
- `scripts/upsert_small_sim_lagoon.py`: alta/actualizacion rapida de `small_sim` en `lagoons`.

## Endpoints Activos

Salud:

- `GET /health`
- `GET /health/live`
- `GET /health/ready`

Auth y RBAC:

- `POST /auth/login`
- `GET /lagoons`
- `PUT /lagoons/{id}`
- `POST /control/pump`

Ingesta:

- `POST /ingest/scada`

El payload acepta `product_type` opcional (`crystal` o `small`). Si viene informado, debe coincidir con `lagoons.product_type`; si no coincide, el backend responde `409 Lagoon product_type mismatch`.

SCADA:

- `GET /scada/{lagoon_id}/realtime`
- `GET /scada/{lagoon_id}/history`
- `GET /scada/{lagoon_id}/kpis`
- `GET /scada/{lagoon_id}/events`
- `GET /scada/{lagoon_id}/pump-events`
- `GET /scada/{lagoon_id}/pump-events/last-3`
- `GET /scada/{lagoon_id}/pump-events/report.xlsx`

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

Alarmas y notificaciones:

- `GET /alarms/{lagoon_id}/thresholds/pt-fit/view`
- `PUT /alarms/{lagoon_id}/thresholds/pt-fit`
- `POST /email/test-alert`

WebSocket:

- `WS /ws/scada/{lagoon_id}`
- `WS /ws/{product_type}/{lagoon_id}` para clientes productizados (`crystal` o `small`)

## Seguridad

- Ingest exige `X-Api-Key`.
- REST protegido exige `Authorization: Bearer <jwt>`.
- WebSocket acepta token por query string o subprotocol.
- Roles soportados: `AdminCrystal`, `VisualCrystal`, `AdminSmall`, `VisualSmall`, `SuperAdmin`.
- Permisos finos por laguna vienen de `vw_user_lagoons`.

## Observabilidad

- `GET /health/ready` reporta DB, watchdog, signal monitor y estadisticas WS.
- Los loggers `alarms.*` pueden escribir en `logs/alarmas.txt`.
- El ingest registra filas de minuto, eventos y transiciones de alarmas.

## Documentacion Mantenida

- `docs/INDEX.md`: mapa de documentacion.
- `docs/ONE_PAGE_SUMMARY.md`: resumen operativo.
- `docs/ARQUITECTURA_Y_FLUJO.md`: arquitectura vigente.
- `docs/FLUJO_INSERCION.md`: flujo de ingest y alta de lagunas.
- `docs/SMALL_LAGOONS.md`: operacion y endpoints Small Lagoons.
- `docs/ALARMAS_ACTUALES_Y_LOGICA.md`: motor de alarmas.
- `docs/EMAIL_NOTIFICATIONS.md`: flujo SMTP.
- `docs/README_ALARM_THRESHOLDS_API.md`: contrato PT/FIT.

## Notas Operativas

- Las notificaciones se despachan siempre post-commit.
- Solo las aperturas (`OPEN`) generan jobs de notificacion automaticos.
- `webhook` sigue simulado; no hay POST HTTP real.
- Si se agrega una laguna o cambia su timezone directamente en BD, reiniciar backend precarga metadata en `RealtimeStateStore`.
