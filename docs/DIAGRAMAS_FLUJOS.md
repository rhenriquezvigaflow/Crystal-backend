# Diagramas de Flujo y Arquitectura - Crystal Lagoons

Este documento contiene representaciones visuales de cómo funciona el sistema.

---

## Arquitectura General del Sistema

```
┌────────────────────────────────────────────────────────────────────┐
│                     CLIENTE EXTERNO (SCADA Device)                 │
│                                                                    │
│  Sensores: Temperatura, Presión, pH, Estados de Bombas            │
└─────────────────────────────────────┬────────────────────────────┘
                                      │
                 ┌────────────────────┼────────────────────┐
                 │                    │                    │
                 ▼                    ▼                    ▼
          ┌────────────┐       ┌─────────────┐    ┌──────────────┐
          │ HTTP POST  │       │ WebSocket   │    │ Query API    │
          │ /ingest    │       │ /ws/scada   │    │ /history     │
          └─────┬──────┘       └──────┬──────┘    └───────┬──────┘
                │                     │                   │
                └──────────┬──────────┼───────────────────┘
                           │          │
                           ▼          ▼
            ┌──────────────────────────────────────┐
            │    ⚡ FastAPI Application            │
            │                                      │
            │  ┌──────────────────────────────┐   │
            │  │ RealtimeStateStore (Memoria) │   │
            │  │ - tags{lagoon → {...}}       │   │
            │  │ - last_ts, pump_last_on      │   │
            │  └──────────────────────────────┘   │
            │           △ △ △                     │
            │           │ │ │                     │
            │  ┌────────┴─┴─┴──────────────────┐  │
            │  │  IngestService                │  │
            │  │  - Bufferiza por minuto       │  │
            │  │  - Detecta eventos       ON/OFF │  │
            │  │  - Guarda en BD               │  │
            │  └────────┬────────────────────┘   │
            │           │                        │
            │  ┌────────▼──────────────────────┐ │
            │  │ WebSocketManager               │ │
            │  │ - Broadcast a clientes        │ │
            │  └────────────────────────────▲──┘ │
            │                               │   │
            └───────────────────────────────┼───┘
                                            │
                          ┌─────────────────┴────────────────┐
                          │     PostgreSQL Database       │
                          │                                 │
                          │  Tablas principales:           │
                          │  ┌─────────────────────────┐   │
                          │  │ scada_event             │   │
                          │  │ - id (UUID)             │   │
                          │  │ - lagoon_id             │   │
                          │  │ - tag_id                │   │
                          │  │ - start_ts (bomba ON)   │   │
                          │  │ - end_ts (bomba OFF)    │   │
                          │  └─────────────────────────┘   │
                          │                                 │
                          │  ┌─────────────────────────┐   │
                          │  │ scada_minute            │   │
                          │  │ - id (BigInt seq)       │   │
                          │  │ - lagoon_id             │   │
                          │  │ - tag_id                │   │
                          │  │ - bucket (minuto)       │   │
                          │  │ - value_num (último)    │   │
                          │  │ - value_bool (último)   │   │
                          │  └─────────────────────────┘   │
                          │                                 │
                          └─────────────────────────────────┘

                                  │
                                  │
                    ┌─────────────┴────────────┐
                    │                          │
                    ▼                          ▼
              ┌──────────────┐        ┌──────────────┐
              │ Navegadores  │        │ Aplicaciones │
              │ (React)      │        │ (Data BI)    │
              └──────────────┘        └──────────────┘
```

---

## 🔄 Flujo Completo de Inserción: Paso a Paso

```
MOMENTO 0: Cliente SCADA genera dato
┌─────────────────────────────────────┐
│ Sensor detecta cambio:              │
│ 🔴 Bomba apagada → 🟢 Bomba encendida
│ Timestamp preciso: 14:30:45.123Z   │
└─────────────────────────────────────┘
                │
                │ POST /ingest/scada
                │ {lagoon: "cl", tags: {bomba: true}}
                ▼

MOMENTO 1: FastAPI recibe request
┌─────────────────────────────────────┐
│ ingest_router.ingest_scada()        │
├─────────────────────────────────────┤
│ 1. Parsear payload                  │
│ 2. Convertir ts a datetime UTC      │
│ 3. Obtener referencias:             │
│    - state_store                    │
│    - ws_manager                     │
│    - db connection                  │
└─────────────────────────────────────┘
                │
                ▼

MOMENTO 2: Actualizar Estado en Memoria
┌─────────────────────────────────────┐
│ RealtimeStateStore.update()         │
├─────────────────────────────────────┤
│ Antes:                              │
│ tags[cl] = {}                       │
│                                     │
│ Después:                            │
│ tags[cl] = {bomba: true}            │
│ last_ts[cl] = 14:30:45.123Z         │
│ pump_last_on[cl] = {                │
│   bomba: 14:30:45.123Z ← NUEVO      │
│ }                                   │
└─────────────────────────────────────┘
                │
                ▼

MOMENTO 3: Procesar Lógica de Ingest
┌─────────────────────────────────────┐
│ ingest_service.ingest()             │
├─────────────────────────────────────┤
│ A. BUFFERIZAR MINUTO ACTUAL         │
│    bucket = 14:30:00Z               │
│    _minute_buffer[(cl, bucket)]     │
│      .bomba = [true]                │
│                                     │
│ B. DETECTAR CAMBIO DE ESTADO        │
│    prev_state[bomba] = false        │
│    current_state[bomba] = true      │
│    Transición: false → true ✅      │
│                                     │
│    ACTION: CREATE EVENT             │
│    INSERT INTO scada_event (        │
│      id = <UUID>,                   │
│      lagoon_id = 'cl',              │
│      tag_id = 'bomba',              │
│      start_ts = 14:30:45.123Z,      │
│      end_ts = NULL,   ← ABIERTO     │
│      created_at = NOW()             │
│    )                                │
│    db.flush() → obtener ID          │
│    _open_event_id[(cl, bomba)]      │
│      = <event_id>                   │
│                                     │
│    Actualizar estado booleano:      │
│    _last_bool_state[(cl, bomba)]    │
│      = true                         │
│                                     │
│ C. FLUSH MINUTOS CERRADOS           │
│    (si llegó dato de minuto 14:31)  │
│    Tomar minuto anterior (14:30)    │
│    Para cada tag:                   │
│      INSERT/UPDATE scada_minute     │
│      bucket = 14:30:00Z             │
│      value_num = <último número>    │
│      value_bool = <último booleano> │
│    _minute_buffer.pop((cl, 14:30))  │
│                                     │
│ D. COMMIT A BASE DE DATOS           │
│    db.commit()  ← PERSIST DONE      │
└─────────────────────────────────────┘
                │
                ▼

MOMENTO 4: Broadcast WebSocket
┌─────────────────────────────────────┐
│ WebSocketManager.broadcast()        │
├─────────────────────────────────────┤
│ Obtener snapshot actualizado:       │
│                                     │
│ await state.tick_payload(cl)        │
│ {                                   │
│   "type": "tick",                   │
│   "lagoon_id": "cl",                │
│   "ts": "14:30:45.123Z",            │
│   "tags": {                         │
│     "bomba": true  ← ACTUALIZADO    │
│   },                                │
│   "pump_last_on": {                 │
│     "bomba": "14:30:45.123Z"        │
│   },                                │
│   "start_ts": {                     │
│     "cl": "14:30:45.123Z"           │
│   }                                 │
│ }                                   │
│                                     │
│ Por cada WebSocket conectado a 'cl'│
│   ws.send_json(payload)             │
│ (Si conexión muere, auto-cleanup)   │
└─────────────────────────────────────┘
                │
                ▼

MOMENTO 5: Respuesta al Cliente HTTP
┌─────────────────────────────────────┐
│ HTTP 200 OK                         │
│ {"ok": true}                        │
│                                     │
│ Tiempo total: ~50-200ms          │
└─────────────────────────────────────┘
                │
                ▼

CLIENTES CONECTADOS RECIBEN PAYLOAD EN TIEMPO REAL
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Cliente Browser  │  │ Cliente Node.js  │  │ Cliente Desktop  │
│                  │  │                  │  │                  │
│ ws.onmessage:    │  │ ws.on('message'):│  │ websocket recv() │
│   tick recibido  │  │   actualizar DB  │  │   log file       │
│                  │  │                  │  │                  │
│ UPDATE UI        │  │ ESCRIBIR LOG     │  │ NOTIFICAR        │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

---

## Ciclo de Vida de un Evento Booleano

```
EVENTO: Bomba Principal

ESTADO 0 - INICIAL
┌───────────────────────────────────────────────────────┐
│ Bomba: OFF (false)                                    │
│ _last_bool_state[(cl, bomba)] = false                 │
│ Tabla scada_event: (vacío)                            │
└───────────────────────────────────────────────────────┘

        14:30:45Z - CAMBIO DETECTADO

        POST /ingest/scada
        tags: {bomba: true}
                   ↓

EVENTO 1 - APERTURA (ON)
┌───────────────────────────────────────────────────────┐
│ Transición: false → true                              │
│                                                       │
│ Acción: INSERT scada_event                            │
│                                                       │
│ scada_event                                           │
│ ┌────────────────────────────────────┐                │
│ │ id: a1b2c3d4                       │                │
│ │ lagoon_id: cl                      │   ← NUEVO      │
│ │ tag_id: bomba                      │                │
│ │ start_ts: 14:30:45Z        ABIERTO                  │
│ │ end_ts: NULL               ACTIVO                   │
│ │ created_at: 14:30:45.323Z          │                │
│ └────────────────────────────────────┘                │
│                                                       │
│ _open_event_id[(cl, bomba)] = "a1b2c3d4"              │
│ _last_bool_state[(cl, bomba)] = true                  │
└───────────────────────────────────────────────────────┘

        15 minutos después...
        14:45:15Z

        POST /ingest/scada
        tags: {bomba: false}
                   ↓

EVENTO 2 - CIERRE (OFF)
┌───────────────────────────────────────────────────────┐
│ Transición: true → false                              │
│                                                       │
│ Acción: UPDATE scada_event WHERE id = a1b2c3d4        │
│         SET end_ts = 14:45:15Z                        │
│                                                       │
│ scada_event (ACTUALIZADO)                             │
│ ┌────────────────────────────────────┐                │
│ │ id: a1b2c3d4                       │                │
│ │ lagoon_id: cl                      │                │
│ │ tag_id: bomba                      │                │
│ │ start_ts: 14:30:45Z       ✅ COMPLETO              │
│ │ end_ts: 14:45:15Z         ✅ FINALIZADO            │
│ │ created_at: 14:30:45.323Z         │                 │
│ │ duration: 14min 30sec               │               │
│ └────────────────────────────────────┘                │
│                                                       │
│ _open_event_id[(cl, bomba)] = (removido)             │
│ _last_bool_state[(cl, bomba)] = false                │
└───────────────────────────────────────────────────────┘

        10 minutos después...

        POST /ingest/scada
        tags: {bomba: true}
                   ↓

EVENTO 3 - NUEVA APERTURA (ON again)
┌───────────────────────────────────────────────────────┐
│ Transición: false → true                              │
│                                                       │
│ Acción: INSERT scada_event (evento NUEVO)             │
│                                                       │
│ scada_event (NUEVO REGISTRO)                          │
│ ┌────────────────────────────────────┐                │
│ │ id: e5f6g7h8                       │                │
│ │ lagoon_id: cl                      │   ← NUEVO     │
│ │ tag_id: bomba                      │                │
│ │ start_ts: 14:55:30Z        ✅ ABIERTO             │
│ │ end_ts: NULL               ✅ ACTIVO              │
│ │ created_at: 14:55:30.741Z         │                │
│ └────────────────────────────────────┘                │
│                                                       │
│ _open_event_id[(cl, bomba)] = "e5f6g7h8"             │
│ _last_bool_state[(cl, bomba)] = true                 │
└───────────────────────────────────────────────────────┘

RESULTADO FINAL EN BD:
┌────────────────────────────────────────────────────────┐
│ scada_event                                            │
├─────┬────┬────────┬────────────┬────────────┬──────────┤
│ id  │lag │tag_id  │ start      │ end        │ duration │
├─────┼────┼────────┼────────────┼────────────┼──────────┤
│ a1b │cl  │bomba   │ 14:30:45Z  │ 14:45:15Z  │ 14m30s   │
│ e5f │cl  │bomba   │ 14:55:30Z  │ NULL       │ ACTIVO   │
└─────┴────┴────────┴────────────┴────────────┴──────────┘
```

---

## Estado en Memoria vs Persistencia

```
┌─────────────────────────────┐
│  RealtimeStateStore         │  ← EN MEMORIA (RAM)
│  (Actualiza al INSTANTE)    │
│                             │
│  {                          │
│    tags: {                  │
│      cl: {                  │
│        bomba: true,     ← Valor ACTUAL
│        temp: 28.5       ← Valor ACTUAL
│      }                      │
│    },                       │
│    last_ts: {               │
│      cl: "14:30:45Z"   ← Último timestamp
│    },                       │
│    pump_last_on: {          │
│      cl: {                  │
│        bomba: "14:30:45Z" ← Cuándo encendió
│      }                      │
│    }                        │
│  }                          │
└─────────────────────────────┘
         │
         │ Se sincroniza con
         ▼

┌─────────────────────────────┐
│  PostgreSQL Database        │  ← PERSISTENCIA (Disco)
│  (PERMANENTE)               │  (Recuperable si crash)
│                             │
│  Tabla: scada_event         │
│  ├─ Eventos booleanos       │
│  ├─ start_ts cuando ON      │
│  ├─ end_ts cuando OFF       │
│  └─ Histórico completo      │
│                             │
│  Tabla: scada_minute        │
│  ├─ Agregados por minuto    │
│  ├─ Último valor del minuto │
│  └─ Series de tiempo        │
│                             │
│  Tabla: scada_alert (future)│
│  ├─ Alertas por umbral      │
│  └─ Auditoría               │
└─────────────────────────────┘
         │
         │ Consultas históricas
         ▼

┌─────────────────────────────┐
│  Dashboard / BI Tools       │
│                             │
│  - Gráficos históricos      │
│  - Reportes por período     │
│  - Estadísticas             │
│  - KPIs                     │
└─────────────────────────────┘
```

---

## WebSocket: Snapshot vs Tick

```
[CLIENTE SE CONECTA]
        │
        ▼
ws://localhost:8000/ws/scada?lagoon_id=cl
        │
        ▼ WebSocketManager.connect()
        │
        │ await ws.send_json(state.snapshot())
        │
        ▼
┌──────────────────────────────┐
│ SNAPSHOT - Estado Actual      │ ← Se envía solo UNA VEZ
├──────────────────────────────┤
│ type: "snapshot"             │
│ lagoon_id: "cl"              │
│ ts: "14:30:45Z"              │
│ tags: {...}                  │
│ pump_last_on: {...}          │
│ start_ts: {...}              │
│                              │
│ Uso: Inicializar UI          │
└──────────────────────────────┘

         Espera...

[NUEVO POST /ingest/scada]
        │
        ├─ Actualizar BD
        ├─ Actualizar RealtimeStateStore
        │
        └─▶ broadcast(lagoon_id, tick_payload)
                │
                ▼
         ┌──────────────────────────────┐
         │ TICK - Actualización          │ ← Se envía cada ingest
         ├──────────────────────────────┤
         │ type: "tick"                 │
         │ lagoon_id: "cl"              │
         │ ts: "14:31:15Z"              │
         │ tags: {...}  ← VALORES NUEVOS│
         │ pump_last_on: {...}          │
         │ start_ts: {...}              │
         │                              │
         │ Uso: Update real-time        │
         └──────────────────────────────┘

         Espera...

[OTRO INGEST]
        │
        └─▶ OTRO TICK enviado

...LOOP infinito hasta desconexión
```

---

## Sincronización Thread-Safe

```
┌────────────────────────────────────────────────────┐
│ POST /ingest/scada (Thread A)                      │
├────────────────────────────────────────────────────┤
│                                                    │
│  with _lock:  ← ADQUIERE LOCK                     │
│    ├─ Lectura de _last_bool_state                 │
│    ├─ Escritura en _minute_buffer                 │
│    ├─ Lectura/Escritura en _open_event_id        │
│  ← LIBERA LOCK                                    │
│                                                    │
└────────────────────────────────────────────────────┘
         ▲
         │ ESPERANDO...
         │

┌────────────────────────────────────────────────────┐
│ POST /ingest/scada (Thread B)                      │
├────────────────────────────────────────────────────┤
│                                                    │
│  with _lock:  ← ESPERA LOCK                       │
│    (bloqueado)                                     │
│                                                    │
│  when lock freed:                                 │
│    ├─ Lectura de _last_bool_state                 │
│    ├─ Escritura en _minute_buffer                 │
│    ├─ Lectura/Escritura en _open_event_id        │
│  ← LIBERA LOCK                                    │
│                                                    │
└────────────────────────────────────────────────────┘

RESULTADO: Acceso serializado, no hay race conditions
```

---

## Diagrama de Almacenamiento de Datos

```
INGEST #1: ts=14:30:45, temp=28.1
    │
    ├─ RealtimeStateStore
    └─ _minute_buffer[(cl, 14:30:00)]["temp"] = [28.1]

INGEST #2: ts=14:30:52, temp=28.3
    │
    ├─ RealtimeStateStore (last_ts actualizado)
    └─ _minute_buffer[(cl, 14:30:00)]["temp"] = [28.1, 28.3]

INGEST #3: ts=14:30:58, temp=28.5
    │
    ├─ RealtimeStateStore (last_ts actualizado)
    └─ _minute_buffer[(cl, 14:30:00)]["temp"] = [28.1, 28.3, 28.5]

INGEST #4: ts=14:31:05, temp=28.4 ← NUEVO MINUTO
    │
    ├─ RealtimeStateStore (last_ts actualizado)
    ├─ _minute_buffer[(cl, 14:31:00)]["temp"] = [28.4]
    │
    └─ FLUSH minuto anterior (14:30:00):
       │
       ├─ Obtener último valor: 28.5
       │
       └─ INSERT INTO scada_minute
          ├─ lagoon_id = 'cl'
          ├─ tag_id = 'temp'
          ├─ bucket = 14:30:00Z
          ├─ value_num = 28.5  ← ÚLTIMO valor
          ├─ value_bool = NULL
          ├─ created_at = NOW()
          └─ updated_at = NOW()

[DESDE AQUÍ EN ADELANTE: 14:30:00 está en BD]

INGEST #5: ts=14:31:12, temp=28.6
    │
    ├─ RealtimeStateStore (last_ts actualizado)
    └─ _minute_buffer[(cl, 14:31:00)]["temp"] = [28.4, 28.6]

[...]

INGEST #6: ts=14:32:03, temp=28.8 ← NUEVO MINUTO
    │
    ├─ RealtimeStateStore (last_ts actualizado)
    ├─ _minute_buffer[(cl, 14:32:00)]["temp"] = [28.8]
    │
    └─ FLUSH minuto anterior (14:31:00):
       │
       ├─ Obtener último valor: 28.6
       │
       └─ INSERT INTO scada_minute
          ├─ lagoon_id = 'cl'
          ├─ tag_id = 'temp'
          ├─ bucket = 14:31:00Z
          ├─ value_num = 28.6  ← ÚLTIMO valor
          ├─ value_bool = NULL
          ├─ created_at = NOW()
          └─ updated_at = NOW()

RESULTADO EN BD (scada_minute):
┌────┬────┬──────────┬──────────┬───────────┬─────────────────┐
│ id │lag │tag_id    │bucket    │value_num  │updated_at       │
├────┼────┼──────────┼──────────┼───────────┼─────────────────┤
│ 1  │cl  │temp      │14:30:00Z │28.5       │2026-02-09...    │
│ 2  │cl  │temp      │14:31:00Z │28.6       │2026-02-09...    │
│ 3  │cl  │temp      │14:32:00Z │28.8       │2026-02-09...    │
└────┴────┴──────────┴──────────┴───────────┴─────────────────┘
```

---

## Matriz de Tipos de Dato

```
┌────────────────────────────────────────────────────────┐
│                  tipos de Datos Soportados              │
├──────────────┬──────────────┬──────────┬──────────┬─────┤
│ Tipo Python  │ JSON         │ En BD    │ Uso      │Notas│
├──────────────┼──────────────┼──────────┼──────────┼─────┤
│ bool         │ true/false   │ BOOLEAN  │ Eventos  │ ON  │
│              │              │          │ON/OFF    │ OFF │
├──────────────┼──────────────┼──────────┼──────────┼─────┤
│ int          │ 123          │ FLOAT    │ Conteos, │Auto │
│              │              │          │ Valores  │conv │
├──────────────┼──────────────┼──────────┼──────────┼─────┤
│ float        │ 28.5         │ FLOAT    │ Temp,PH, │✓    │
│              │              │          │ Presión  │     │
├──────────────┼──────────────┼──────────┼──────────┼─────┤
│ str          │ "error"      │ VARCHAR  │ Estados  │TODO │
│              │              │ (future) │ Texto    │     │
├──────────────┼──────────────┼──────────┼──────────┼─────┤
│ None         │ null         │ NULL     │ Sin datos│Skip │
└──────────────┴──────────────┴──────────┴──────────┴─────┘
```

---

##  Escalabilidad y Límites

```
┌─────────────────────────────────────────────────────┐
│            CAPACIDAD vs CARGA                       │
├──────────────────────┬──────────────────────────────┤
│ Métrica              │ Recomendación                │
├──────────────────────┼──────────────────────────────┤
│ Ingest rate          │ 1-100 msg/sec per lagoon ✓   │
│ Lagunas simultáneas  │ 10-20 sin problemas ✓        │
│ WS clientes/laguna   │ 50-100 cómodo ✓              │
│                      │ 100-500 monitorear ⚠️        │
│ Buffer en memoria    │ maxsize=200k msgs ✓          │
│ Índices BD           │ CRÍTICOS para >1M rows ⚠️    │
│ Pool conexiones      │ 20-50 (ajustar en ini)      │
│ Rows scada_event     │ ~10k por laguna/año ✓       │
│ Rows scada_minute    │ 1440 por laguna/día ✓       │
│                      │ ~500k por lagoon/año ✓      │
└──────────────────────┴──────────────────────────────┘

PARA ESCALAR A MÁS LAGUNAS:
├─ Opción 1: Múltiples instancias FastAPI (load balancer)
├─ Opción 2: Queue centralizada (Redis/RabbitMQ)
├─ Opción 3: Sharding por lagoon_id
└─ Opción 4: CQRS pattern (separar read/write)
```

---

## 🔄 Ciclo de Vida de la Aplicación

```
START: python -m uvicorn app.main:app
        │
        ▼
    ┌──────────────────────────────────────┐
    │ Fase 1: LIFESPAN STARTUP             │
    ├──────────────────────────────────────┤
    │ ✓ Crear RealtimeStateStore (singleton)
    │ ✓ Crear WebSocketManager (singleton)
    │ ✓ Conectar a PostgreSQL              │
    │ ✓ Precargar últimos pump_last_on     │
    │ ✓ Iniciar PersistWorker              │
    │ ✓ Registrar routers (HTTP, WS)       │
    └──────────────────────────────────────┘
        │
        ▼
    ✓ APLICACIÓN LISTA
    │ Escuchando en 0.0.0.0:8000
    │ POST /ingest/scada funciona
    │ WebSocket /ws/scada funciona
    │
    ⏱️ UPTIME: 5 horas, 2 minutos
    │ Ingest procesados: 18,342
    │ clientes WS activos: 3
    │ Eventos abiertos: 7
    │
SHUTDOWN: Ctrl+C
        │
        ▼
    ┌──────────────────────────────────────┐
    │ Fase 2: LIFESPAN CLEANUP             │
    ├──────────────────────────────────────┤
    │ ✓ Detener PersistWorker              │
    │ ✓ Cerrar conexión PostgreSQL         │
    │ ✓ Cerrar conexiones WebSocket        │
    │ ✓ Guardar estado (if needed)         │
    └──────────────────────────────────────┘
        │
        ▼
    ✓ SHUTDOWN CLEAN
    │ Todos los datos persistidos en BD
    │ Próximo inicio: recupera estado
```

---

**Nota:** Estos diagramas representan el flujo actual de la aplicación. 
La arquitectura puede adaptarse según nuevas necesidades.

Última actualización: 2026-02-09
