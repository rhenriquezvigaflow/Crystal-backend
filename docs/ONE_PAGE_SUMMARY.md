# One-Page Summary - Crystal Lagoons Backend

**Version doc:** 1.2
**Actualizado:** 2026-03-13

---

## Arquitectura en 30 segundos

```text
SCADA Collector --(POST /ingest/scada + x-api-key)--> FastAPI
                                                      |
                                                      +--> RealtimeStateStore (memoria)
                                                      +--> IngestService (eventos + scada_minute)
                                                      +--> WebSocketManager (broadcast por laguna)
                                                      +--> PostgreSQL
```

El backend tambien expone:

- Login JWT (`POST /auth/login`).
- Lecturas SCADA (`/scada/*`).
- RBAC por permisos de laguna (`/lagoons`, `/control/pump`).
- APIs por producto (`/api/crystal/*`, `/api/small/*`).
- WebSockets autenticados (`/ws/*`).

---

## Flujo principal

1. `POST /ingest/scada` recibe `{lagoon_id, timestamp?, tags}`.
2. El servicio persiste cambios de estado y flush por minuto en BD.
3. Se actualiza `RealtimeStateStore`.
4. Se emite `tick` por websocket para la laguna.
5. Respuesta HTTP: `{"ok": true}`.

---

## Seguridad

Ingest:

- Header obligatorio: `x-api-key: <COLLECTOR_API_KEY>`.

API de usuarios:

- Login: `POST /auth/login`.
- Resto de endpoints protegidos usan `Authorization: Bearer <token>`.

Roles soportados:

- `AdminCrystal`
- `VisualCrystal`
- `AdminSmall`
- `VisualSmall`

Permisos por laguna (vista `vw_user_lagoons`):

- `can_view`
- `can_edit`
- `can_control`

---

## Endpoints clave

Publicos:

- `GET /health`
- `POST /auth/login`

Ingest:

- `POST /ingest/scada`

SCADA general:

- `GET /scada/{lagoon_id}/current`
- `GET /scada/{lagoon_id}/last-minute`
- `GET /scada/{lagoon_id}/pump-events/last-3`
- `GET /scada/history/{resolution}`

RBAC por permisos:

- `GET /lagoons`
- `PUT /lagoons/{id}`
- `POST /control/pump`

Producto Crystal:

- `GET /api/crystal/lagoons`
- `GET /api/crystal/dashboard`
- `GET /api/crystal/lagoons/{lagoon_id}/current`
- `GET /api/crystal/lagoons/{lagoon_id}/last-minute`
- `GET /api/crystal/lagoons/{lagoon_id}/pump-events/last-3`
- `GET /api/crystal/history`
- `GET|PUT|DELETE /api/crystal/layout`
- `GET|PUT|DELETE /api/crystal/tags`

Producto Small:

- `GET /api/small/lagoons`
- `GET /api/small/dashboard`
- `GET /api/small/lagoons/{lagoon_id}/current`
- `GET /api/small/lagoons/{lagoon_id}/last-minute`
- `GET /api/small/lagoons/{lagoon_id}/pump-events/last-3`
- `GET /api/small/history`
- `POST|PUT /api/small/control`
- `GET|POST|DELETE /api/small/chemicals`

WebSocket:

- `WS /ws/scada?lagoon_id=<id>&token=<jwt>`
- `WS /ws/scada/{lagoon_id}?token=<jwt>`
- `WS /ws/crystal/{lagoon_id}?token=<jwt>`
- `WS /ws/small/{lagoon_id}?token=<jwt>`

---

## Payloads

Ingest input:

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

WebSocket snapshot/tick:

```json
{
  "type": "tick",
  "lagoon_id": "laguna_1",
  "ts": "2026-03-13T14:30:45+00:00",
  "plc_status": "online",
  "local_time": "11:30:45",
  "timezone": "America/Santiago",
  "tags": {
    "bomba_1": 1,
    "temperatura": 28.5
  },
  "pump_last_on": {
    "bomba_1": "2026-03-13T14:30:45+00:00"
  },
  "start_ts": "2026-03-13T14:30:45+00:00"
}
```

---

## Base de datos

Tablas principales:

- `scada_event`: cambios de estado y duracion.
- `scada_minute`: ultimo valor por `(lagoon_id, tag_id, bucket)`.
- `lagoons`: catalogo de lagunas, timezone y `product_type`.
- `users`, `roles`, `user_roles`: RBAC.

Vistas usadas por backend:

- `vw_scada_last_3_pump_actions`
- `vw_user_lagoons`
- `scada_minute_hourly|daily|weekly` (si existen)

---

## Setup minimo

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# .env
# DATABASE_URL=...
# COLLECTOR_API_KEY=...
# JWT_SECRET_KEY=...

python -m uvicorn app.main:app --reload
```

Scripts utiles:

- `psql "$DATABASE_URL" -f scripts/sql/create_rbac_tables.sql`
- `python scripts/seed_roles.py`
- `psql "$DATABASE_URL" -f scripts/sql/create_scada_continuous_aggregates.sql`

---

Mas detalle:

- [ARQUITECTURA_Y_FLUJO.md](./ARQUITECTURA_Y_FLUJO.md)
- [GUIA_TECNICA_DESARROLLO.md](./GUIA_TECNICA_DESARROLLO.md)
