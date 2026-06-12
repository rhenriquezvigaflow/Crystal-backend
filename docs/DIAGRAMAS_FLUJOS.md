# Diagramas de Flujos - Crystal Lagoons Backend

**Ultima actualizacion:** 2026-06-12  
**Version:** 2.0

## 1. Arquitectura General

```text
                +-------------------------+
Collector ----> | POST /ingest/scada      |
(X-Api-Key)     | FastAPI                 |
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
User UI ----> GET /{product}/lagoons, /{product}/history, /alarms/* (Bearer)
User UI ----> WS /ws/{product}/{lagoon_id} (token + can_view)
```

## 2. Flujo de Ingest

```text
POST /ingest/scada
  |
  +--> validar X-Api-Key
  +--> validar laguna habilitada y product_type si viene
  +--> parse timestamp UTC
  +--> sync opcional sp_sync_collector_tags_and_alarms
  +--> persistir en thread (timeout)
        |
        +--> detectar cambios de estado
        +--> cerrar evento abierto si existe
        +--> crear nuevo evento STATE_CHANGE
        +--> upsert scada_minute
  +--> evaluar alarmas
  +--> commit
  +--> despachar notificaciones post-commit
  +--> actualizar RealtimeStateStore
  +--> broadcast websocket por laguna
  '--> 200 {"ok": true}
```

## 3. Flujo WebSocket

```text
Cliente WS conecta a /ws/{product}/{lagoon_id}
  |
  +--> validar JWT
  +--> validar permiso can_view o alcance por producto
  +--> aceptar conexion
  +--> enviar snapshot inicial
  '--> mantener conexion y enviar tick en cada ingest
```

Endpoint:

- `/ws/{product}/{lagoon_id}?token=<jwt>`

## 4. Flujo de Historico

```text
GET /{product}/history?lagoon_id={lagoon_id}
  |
  +--> resolution: hourly|daily|weekly
  +--> existe vista scada_minute_<resolution> ?
        | yes                     | no
        v                         v
      query view             fallback scada_minute
      source="view"          source="table"
  '--> respuesta con series por tag
```

## 5. Startup Lifecycle

```text
App start
  |
  +--> crear RealtimeStateStore
  +--> crear WebSocketManager
  +--> cargar timezones desde lagoons
  +--> precargar pump_last_on desde scada_event
  +--> iniciar ScadaStallWatchdog
  +--> iniciar AlarmLagoonSignalMonitor
  '--> listo para trafico

App stop
  +--> detener AlarmLagoonSignalMonitor
  '--> detener ScadaStallWatchdog
```

## 6. Seguridad Resumida

```text
Ingest: X-Api-Key
REST protegido: Bearer JWT + roles/permisos
WS: token + can_view por laguna
```

Roles:

- AdminCrystal
- VisualCrystal
- AdminSmall
- VisualSmall
- SuperAdmin

Permisos:

- can_view
- can_edit
- can_control
