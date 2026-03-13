# Diagramas de Flujos - Crystal Lagoons Backend

**Ultima actualizacion:** 2026-03-13
**Version:** 1.2

---

## 1) Arquitectura general

```text
                +-------------------------+
Collector ----> | POST /ingest/scada      |
(x-api-key)     | (FastAPI)               |
                +-----------+-------------+
                            |
                            v
                   +--------+---------+
                   | IngestService    |
                   | - eventos        |
                   | - scada_minute   |
                   +--------+---------+
                            |
                            v
                       PostgreSQL

User UI ----> POST /auth/login ----> JWT
User UI ----> GET /scada/*, /api/* (Bearer)
User UI ----> WS /ws/* (token + can_view)
```

---

## 2) Flujo de ingest

```text
POST /ingest/scada
  |
  +--> validar x-api-key
  +--> parse timestamp UTC
  +--> persistir en thread (timeout)
        |
        +--> detectar cambios de estado
        +--> cerrar evento abierto (si existe)
        +--> crear nuevo evento STATE_CHANGE
        +--> upsert scada_minute en buckets cerrados
  +--> actualizar RealtimeStateStore
  +--> broadcast websocket por laguna
  '--> 200 {"ok": true}
```

---

## 3) Flujo websocket

```text
Cliente WS conecta con lagoon_id + token
  |
  +--> validar JWT
  +--> validar permiso can_view en vw_user_lagoons
  +--> aceptar conexion
  +--> enviar snapshot inicial
  '--> mantener conexion y enviar tick en cada ingest
```

Endpoints:

- `/ws/scada?lagoon_id=<id>&token=<jwt>`
- `/ws/scada/{lagoon_id}?token=<jwt>`
- `/ws/crystal/{lagoon_id}?token=<jwt>`
- `/ws/small/{lagoon_id}?token=<jwt>`

---

## 4) Flujo de historial

```text
GET /scada/history/{resolution}
  |
  +--> resolution: hourly|daily|weekly
  +--> existe vista scada_minute_<resolution> ?
        | yes                     | no
        v                         v
      query view             time_bucket(scada_minute)
      source="view"          source="table"
  '--> respuesta con series por tag
```

Producto-specifico:

- `GET /api/crystal/history`
- `GET /api/small/history`

Si no envias `resolution`, el backend la elige por rango de fechas.

---

## 5) Startup lifecycle

```text
App start
  |
  +--> crear RealtimeStateStore
  +--> crear WebSocketManager
  +--> cargar timezones desde lagoons
  +--> precargar pump_last_on desde vw_scada_last_3_pump_actions
  +--> iniciar ScadaStallWatchdog
  '--> listo para trafico

App stop
  '--> detener ScadaStallWatchdog
```

---

## 6) Seguridad resumida

```text
Ingest: x-api-key
REST protegido: Bearer JWT + roles/permisos
WS: token (query/header) + can_view por laguna
```

Roles:

- AdminCrystal
- VisualCrystal
- AdminSmall
- VisualSmall

Permisos:

- can_view
- can_edit
- can_control
