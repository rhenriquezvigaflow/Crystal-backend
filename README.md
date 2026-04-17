# Crystal Lagoons - SCADA Backend

Backend FastAPI para ingesta SCADA, lectura realtime, historico, layouts dinamicos y motor de alarmas.

## Alcance actual

- `POST /ingest/scada` protegido con `X-Api-Key`.
- estado realtime en memoria + broadcast WebSocket.
- persistencia de `scada_minute` y `scada_event`.
- consultas SCADA (`current`, `last-minute`, `history`, `events`, `pump-events`).
- RBAC por laguna para lectura, edicion y control.
- layouts backend-driven (`layouts` + `lagoon_layout_mapping`).
- alarmas `state`, `comm_loss` y `threshold`.
- notificaciones por email reales via SMTP y webhook simulado por log.

## Como se integra con frontend y collector

```text
collector_python
  -> POST /ingest/scada
  -> evaluate_alarms()
  -> commit DB
  -> dispatch_notifications()
  -> state_store + ws_manager
  -> crystal-frontend
```

## Nota sobre prefijos `/api`

El backend define rutas sin prefijo en codigo (`/health`, `/scada/...`, `/alarms/...`), pero la app corre con `root_path="/api"` para despliegues detras de proxy.

En practica:

- backend directo local: `/health`, `/scada/...`
- frontend o proxy IIS/Vite: `/api/health`, `/api/scada/...`

## Puesta en marcha

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

## Modulos principales

- `app/main.py`: bootstrap, CORS, lifespan, watchdog, signal monitor.
- `app/routers/ingest.py`: entrada de telemetria del collector.
- `app/services/ingest_service.py`: minute buffers y eventos SCADA.
- `app/alarms/service.py`: evaluacion y transiciones OPEN/CLOSE.
- `app/integration/notifications.py`: orquestador de canales.
- `app/services/email_service.py`: render de plantilla y envio SMTP.
- `app/routers/scada_layouts.py`: layouts y mapping por laguna.
- `app/routers/scada.py`, `scada_read.py`, `events.py`: lectura HTTP.
- `app/routers/websocket.py`: WebSocket autenticado por laguna.

## Endpoints clave

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

SCADA:

- `GET /scada/{lagoon_id}/last-minute`
- `GET /scada/{lagoon_id}/current`
- `GET /scada/{lagoon_id}/realtime`
- `GET /scada/{lagoon_id}/kpis`
- `GET /scada/{lagoon_id}/history`
- `GET /scada/{lagoon_id}/events`
- `GET /scada/{lagoon_id}/pump-events`
- `GET /scada/{lagoon_id}/pump-events/last-3`

Layouts:

- `GET /layouts/{layout_id}`
- `GET /lagoons/{lagoon_id}/mapping`
- `PUT /lagoons/{lagoon_id}/mapping`

Alarmas y notificaciones:

- `GET /alarms/{lagoon_id}/thresholds/pt-fit/view`
- `PUT /alarms/{lagoon_id}/thresholds/pt-fit`
- `POST /email/test-alert`

WebSocket:

- `WS /ws/scada/{lagoon_id}`

## Documentacion mantenida

- `docs/INDEX.md`: mapa de documentacion.
- `docs/ALARMAS_ACTUALES_Y_LOGICA.md`: motor de alarmas y enrutamiento.
- `docs/EMAIL_NOTIFICATIONS.md`: flujo SMTP, payload y endpoint manual.
- `docs/README_ALARM_THRESHOLDS_API.md`: contrato PT/FIT.

## Observabilidad

- `GET /health/ready` reporta estado de DB, watchdog, signal monitor y estadisticas WS.
- los loggers `alarms.*` pueden escribir en `logs/alarmas.txt`.
- el ingest registra filas de minuto, eventos y transiciones de alarmas.

## Notas operativas

- las notificaciones se despachan siempre post-commit.
- solo las aperturas (`OPEN`) generan jobs de notificacion automaticos.
- `webhook` sigue simulado; no hay POST HTTP real.
- el frontend actual consume estas rutas via `/api/*` detras de proxy.
