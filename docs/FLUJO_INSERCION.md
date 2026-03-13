# Flujo de Insercion y Publicacion SCADA

**Version doc:** 1.2
**Actualizado:** 2026-03-13

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
5. Se actualiza `RealtimeStateStore`.
6. Se emite `tick` via websocket para esa laguna.
7. Respuesta `200 {"ok": true}`.

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

## 7) WebSocket operativo

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

## 8) Dependencias de seguridad

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
