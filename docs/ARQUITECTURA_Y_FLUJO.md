# 📐 Arquitectura y Flujo de Inserción de Datos - Crystal Lagoons

**Última actualización:** Febrero 2026  
**Versión:** 1.0

---

## 📋 Tabla de Contenidos

1. [Visión General](#visión-general)
2. [Componentes Principales](#componentes-principales)
3. [Flujo de Inserción de Datos](#flujo-de-inserción-de-datos)
4. [Endpoints HTTP](#endpoints-http)
5. [Sistema WebSocket (Real-time)](#sistema-websocket-real-time)
6. [Modelos de Base de Datos](#modelos-de-base-de-datos)
7. [Estado y Sincronización](#estado-y-sincronización)
8. [Diagramas de Arquitectura](#diagramas-de-arquitectura)

---

## 🎯 Visión General

**Crystal Lagoons** es una aplicación **FastAPI** que ingiere datos SCADA de lagunas en tiempo real. El sistema:

- Recibe datos de sensores (tags) a través de un **endpoint HTTP POST**
- Almacena los datos en **PostgreSQL** de forma persistente
- Mantiene un **estado en memoria** de los últimos valores
- Envía actualizaciones en **tiempo real** al frontend a través de **WebSocket**
- Procesa eventos booleanos (bomba ON/OFF) con timestamps precisos

### Stack Tecnológico

```
Frontend (React/Vue) 
    ↓ HTTP POST
    ↓ WebSocket
    ↓
FastAPI Backend (Python)
    ↓
PostgreSQL
```

---

## 🧩 Componentes Principales

### 1. **FastAPI Application** (`app/main.py`)

Punto de entrada de la aplicación. Inicializa:

```python
# Singletons (creados una sola vez al iniciar)
- RealtimeStateStore      # Estado en memoria de última lectura
- WebSocketManager        # Gestor de conexiones WebSocket
- PersistWorker          # Worker para persistir datos asincronamente
```

**Ciclo de vida:**

```
🟢 BOOT
├─ Cargar último estado de BD (pump_last_on)
├─ Iniciar PersistWorker
└─ Listo para recibir datos

🔴 SHUTDOWN
└─ Detener PersistWorker
```

---

### 2. **Ingest Router** (`app/routers/ingest.py`)

Endpoint HTTP que recibe datos SCADA.

#### Endpoint: `POST /ingest/scada`

**Payload:**
```json
{
  "lagoon_id": "costa_del_lago",
  "ts": "2026-02-09T14:30:45Z",  
  "tags": {
    "bomba_1": true,
    "temperatura": 28.5,
    "presion": 2.3
  }
}
```

**Flujo de procesamiento:**

```
POST /ingest/scada
    ↓
1. Parsear timestamp 
2. Actualizar RealtimeStateStore 
    ↓
3. Llamar a ingest_service.ingest()
    ├─ Bufferizar valores en minutos
    ├─ Crear/cerrar eventos booleanos
    └─ Persistir en BD
    ↓
4. Broadcast a WebSocket 
    ↓
200 OK
```

---

### 3. **Ingest Service** (`app/services/ingest_service.py`)

Core de la lógica de procesamiento. Maneja:

#### A. **Buffering por minutos**

Los datos se agrupan en buckets de **1 minuto** para optimizar almacenamiento:

```python
_minute_buffer: Dict[Tuple[lagoon_id, bucket_time], Dict[tag_id, [valores]]]

Ejemplo:
("costa_del_lago", "2026-02-09T14:30:00Z") → {
  "temperatura": [28.1, 28.3, 28.5],
  "presion": [2.1, 2.2, 2.3]
}
```

**Estrategia de flush:**
- Cuando llega un dato de un minuto más reciente → flush del minuto anterior
- Se guarda el **último valor** del minuto en `ScadaMinute`

```python
# De [28.1, 28.3, 28.5] → guarda 28.5 en BD
last_val = values[-1]
```

#### B. **Manejo de Eventos Booleanos**

Track de cambios de estado (False → True o True → False):

```python
# Transición ABIERTO (False/None → True)
@broadcaster:pump OFF → Crear novo ScadaEvent con start_ts
└─ _open_event_id[(lagoon_id, tag_id)] = event.id

# Transición CERRADO (True → False)
@broadcast: pump ON → Cerrar ScadaEvent con end_ts
└─ Actualizar registro existente con end_ts
```

**Estado persistente:**
```python
_last_bool_state: Dict[(lagoon_id, tag_id), bool]  # Último estado conocido
_open_event_id:   Dict[(lagoon_id, tag_id), id]    # ID del evento abierto
```

---

### 4. **WebSocket Manager** (`app/ws/manager.py`)

Gestor de conexiones bidireccionales:

```python
class WebSocketManager:
    _connections: Dict[lagoon_id, Set[WebSocket]]
    
    async def connect(lagoon_id, ws)      # Agregar cliente
    async def disconnect(lagoon_id, ws)   # Remover cliente
    async def broadcast(lagoon_id, msg)   # Enviar a TODOS los clientes
```

**Características:**
- ✅ Thread-safe (usa asyncio.Lock)
- ✅ Auto-cleanup de conexiones muertas
- ✅ Broadcasting por laguna (solo a clientes interesados)

---

### 5. **Realtime State Store** (`app/state/store.py`)

Estado compartido en memoria que actúa como "cache" del último tick:

```python
class RealtimeStateStore:
    tags: Dict[lagoon_id, Dict[tag_id, valor]]        # Valores actuales
    last_ts: Dict[lagoon_id, str]                      # Último timestamp
    pump_last_on: Dict[lagoon_id, Dict[tag_id, ts]]   # Último time ON
    start_ts: Dict[lagoon_id, str]                     # Inicio de ciclo
```

**Uso:**
```python
# Cuando llega un ingest
await state.update(lagoon_id, tags, ts_iso)

# Cuando se conecta un WebSocket (snapshot inicial)
state.snapshot(lagoon_id)

# Cuando se broadcast (estado actualizado)
await state.tick_payload(lagoon_id)
```

---

## 🔄 Flujo de Inserción de Datos

### Diagrama de Secuencia

```
CLIENTE SCADA → POST /ingest/scada
    │
    └─→ [1] ingest_router.ingest_scada()
        │
        ├─→ [2] RealtimeStateStore.update()
        │       └─ Actualizar tags, last_ts, pump_last_on
        │
        ├─→ [3] ingest_service.ingest()
        │       ├─ Bufferizar datos de minuto actual
        │       ├─ Detectar cambios booleanos (eventos)
        │       │  ├─ Si False→True: INSERT ScadaEvent (abierto)
        │       │  └─ Si True→False: UPDATE ScadaEvent (cerrado)
        │       │
        │       └─ Flush minutos anteriores cerrados
        │           └─ INSERT/UPDATE ScadaMinute (agregado por minuto)
        │
        ├─→ [4] Commit a PostgreSQL 
        │
        └─→ [5] WebSocketManager.broadcast()
            └─ Enviar tick_payload a TODOS los WebSocket conectados
                │
                └─→ CLIENTES WS ← JSON actualizado (real-time)
```

### Ejemplo Paso a Paso

**Entrada:**
```json
POST /ingest/scada

{
  "lagoon_id": "costa_del_lago",
  "ts": "2026-02-09T14:30:45Z",
  "tags": {
    "bomba_1": true,
    "temperatura": 28.5
  }
}
```

**Paso 1 - Actualizar Estado**
```python
RealtimeStateStore:
  tags["costa_del_lago"] = {"bomba_1": true, "temperatura": 28.5}
  last_ts["costa_del_lago"] = "2026-02-09T14:30:45Z"
```

**Paso 2 - Procesar Ingest**
```python
minute_buffer[("costa_del_lago", 2026-02-09T14:30:00Z)] = {
  "bomba_1": [true],
  "temperatura": [28.5]
}

# Evento: bomba_1 anteriormente OFF → ahora ON
_last_bool_state[("costa_del_lago", "bomba_1")] = False (anterior)
                                                    ↓
# Crear evento abierto
INSERT INTO scada_event (id, lagoon_id, tag_id, start_ts, end_ts)
VALUES (uuid(), "costa_del_lago", "bomba_1", "2026-02-09T14:30:45Z", NULL)

_last_bool_state[("costa_del_lago", "bomba_1")] = True (nuevo)
```

**Paso 3 - Broadcast WebSocket**
```json
{
  "type": "tick",
  "lagoon_id": "costa_del_lago",
  "ts": "2026-02-09T14:30:45Z",
  "tags": {
    "bomba_1": true,
    "temperatura": 28.5
  },
  "pump_last_on": {
    "bomba_1": "2026-02-09T14:30:45Z"
  },
  "start_ts": {
    "costa_del_lago": "2026-02-09T14:30:45Z"
  }
}
```

---

## 🌐 Endpoints HTTP

### 1. Health Check

**Endpoint:** `GET /health`

```bash
curl http://localhost:8000/health
```

**Respuesta:** 
```json
{"status": "ok"}
```

---

### 2. Ingest SCADA

**Endpoint:** `POST /ingest/scada`

**Descripción:** Ingiere datos de sensores SCADA

**Body (JSON):**
```python
{
  "lagoon_id": str,              
  "ts": str | None,              
  "tags": dict[str, Any]         
}
```

**Ejemplos:**

```bash
# Con timestamp especificado
curl -X POST http://localhost:8000/ingest/scada \
  -H "Content-Type: application/json" \
  -d '{
    "lagoon_id": "costa_del_lago",
    "ts": "2026-02-09T14:30:45Z",
    "tags": {
      "bomba_1": true,
      "temperatura": 28.5,
      "presion": 2.3
    }
  }'

# Sin timestamp (usa hora actual)
curl -X POST http://localhost:8000/ingest/scada \
  -H "Content-Type: application/json" \
  -d '{
    "lagoon_id": "costa_del_lago",
    "tags": {
      "bomba_1": false
    }
  }'
```

**Respuesta:** 
```json
{"ok": true}
```

**Errores:**
- `422` - Payload inválido
- `500` - Error al guardar en BD

---

### 3. Historial SCADA

**Endpoint:** `GET /scada/history`

[Versión simplificada - ver `app/scada/history/router.py` para detalles]

---

## 🔌 Sistema WebSocket (Real-time)

### Conexión WebSocket

**Endpoint:** `WebSocket /ws/scada`

**Parámetro de Query:**
```
ws://localhost:8000/ws/scada?lagoon_id=costa_del_lago
```

### Flujo de Conexión

#### 1. **Conectarse**

```javascript
// Cliente JavaScript
const ws = new WebSocket(
  'ws://localhost:8000/ws/scada?lagoon_id=costa_del_lago'
);

ws.onopen = () => console.log('Conectado');
ws.onmessage = (evt) => console.log('Datos:', JSON.parse(evt.data));
ws.onclose = () => console.log('Desconectado');
ws.onerror = (evt) => console.error('Error:', evt);
```

#### 2. **Recibir Snapshot Inicial**

Inmediatamente después de conectarse:

```json
{
  "type": "snapshot",
  "lagoon_id": "costa_del_lago",
  "ts": "2026-02-09T14:30:00Z",
  "tags": {
    "bomba_1": true,
    "temperatura": 28.5
  },
  "pump_last_on": {
    "bomba_1": "2026-02-09T14:29:15Z"
  },
  "start_ts": {
    "costa_del_lago": "2026-02-09T14:29:15Z"
  }
}
```

**Uso:** Inicializar UI con estado actual

#### 3. **Recibir Ticks (Actualizaciones)**

Cuando llega un nuevo `POST /ingest/scada`:

```json
{
  "type": "tick",
  "lagoon_id": "costa_del_lago",
  "ts": "2026-02-09T14:31:15Z",
  "tags": {
    "bomba_1": true,
    "temperatura": 28.6
  },
  "pump_last_on": {
    "bomba_1": "2026-02-09T14:30:45Z"
  },
  "start_ts": {
    "costa_del_lago": "2026-02-09T14:30:45Z"
  }
}
```

**Uso:** Actualizar UI en tiempo real

#### 4. **Desconectar**

```javascript
ws.close();
```

El servidor automáticamente remueve la conexión de su registro.

### Características WebSocket

| Feature | Descripción |
|---------|-------------|
| **Protocol** | RFC 6455 (WebSocket estándar) |
| **Per-lagoon** | Cada laguna tiene su propio broadcast list |
| **Auto-cleanup** | Desconexiones muertas se detectan automáticamente |
| **Thread-safe** | Usa asyncio.Lock para evitar race conditions |
| **No bidireccional** | Solo servidor → cliente |

---

## 📊 Modelos de Base de Datos

### 1. **ScadaEvent** (Eventos de Bombas)

Tabla: `scada_event`

```sql
id              UUID PRIMARY KEY
lagoon_id       VARCHAR(64) FK → lagoons.id
tag_id          VARCHAR(64) INDEX
tag_label       VARCHAR(128)
start_ts        TIMESTAMP WITH TIMEZONE
end_ts          TIMESTAMP WITH TIMEZONE (NULL si abierto)
created_at      TIMESTAMP WITH TIMEZONE
```

**Características:**
- ✅ Eventos de ON/OFF de bombas
- ✅ `end_ts` = NULL → Evento abierto (bomba activa)
- ✅ Índice especial en eventos abiertos: `ix_scada_event_open`

**Ejemplo:**
```
| id | lag | tag | start_ts | end_ts | created_at |
|----|-----|-----|----------|--------|-----------|
| 1  | cl  | b1  | 14:30:00 | 14:45:00 | ... | (ciclo completo)
| 2  | cl  | b1  | 14:50:00 | NULL   | ... | (abierto, ON)
```

---

### 2. **ScadaMinute** (Agregados por Minuto)

Tabla: `scada_minute`

```sql
id              BIGINT PRIMARY KEY AUTOINCREMENT
lagoon_id       VARCHAR(64) FK → lagoons.id
tag_id          VARCHAR(64)
bucket          TIMESTAMP WITH TIMEZONE (truncado a minuto)
value_num       FLOAT (NULL si es booleano)
value_bool      BOOLEAN (NULL si es número)
created_at      TIMESTAMP WITH TIMEZONE
updated_at      TIMESTAMP WITH TIMEZONE
```

**Índices:**
```
UNIQUE (lagoon_id, tag_id, bucket)    ← Evita duplicados
INDEX (bucket)
INDEX (lagoon_id)
```

**Características:**
- Una fila por minuto/tag
- Guarda el **último valor** del minuto
- Optimizado para queries de histórico
- ON CONFLICT → UPDATE (actualizar si existe)

**Ejemplo:**
```
| id | lagoon_id | tag_id | bucket | value_num | value_bool | updated_at |
|----|-----------|--------|--------|-----------|-----------|-----------|
| 1  | cl | temp | 14:30:00 | 28.5 | NULL | 2026-02-09 14:30:45 |
| 2  | cl | bomba | 14:30:00 | NULL | true | 2026-02-09 14:30:45 |
| 3  | cl | temp | 14:31:00 | 28.6 | NULL | 2026-02-09 14:31:15 |
```

---

## 🗄️ Estado y Sincronización

### RealtimeStateStore (Memoria)

**Contenidos:**

```python
{
  "tags": {
    "costa_del_lago": {
      "bomba_1": True,
      "temperatura": 28.5,
      "presion": 2.3
    }
  },
  "last_ts": {
    "costa_del_lago": "2026-02-09T14:30:45Z"
  },
  "pump_last_on": {
    "costa_del_lago": {
      "bomba_1": "2026-02-09T14:30:45Z"
    }
  },
  "start_ts": {
    "costa_del_lago": "2026-02-09T14:30:45Z"
  }
}
```

**Precarga al BOOT:**

```python
# main.py - lifespan startup
db = SessionLocal()
last_start_by_pump = ScadaEventRepository.get_last_start_ts_by_lagoon(
  db, lagoon_id="costa_del_lago"
)
app.state.state_store.pump_last_on["costa_del_lago"] = last_start_by_pump
```

Query:
```sql
SELECT tag_id, MAX(start_ts) as start_ts
FROM scada_event
WHERE lagoon_id = 'costa_del_lago'
GROUP BY tag_id
```

### Sincronización en Tiempo Real

```
Ingest → RealtimeStateStore ← WebSocket payload
         ↓
         PostgreSQL (persistencia)
```

**Garantías:**
- Cada POST /ingest/scada actualiza estado + BD + WS
- RealtimeStateStore siempre refleja el último ingest
- Reconexión WS recibe snapshot actualizado

---

## 📈 Diagramas de Arquitectura

### Diagrama 1: Componentes Principales

```
┌─────────────────────────────────────────────────────┐
│         Frontend (React/Vue)                        │
│  ┌────────────────┐          ┌──────────────────┐  │
│  │ HTTP Client    │          │ WebSocket Client │  │
│  └────────┬───────┘          └────────┬─────────┘  │
└───────────┼──────────────────────────┼─────────────┘
            │ POST /ingest/scada       │ ws://...
            ▼                          ▼
┌─────────────────────────────────────────────────────┐
│           FastAPI Backend (Python)                  │
│                                                     │
│  ┌──────────────────┐    ┌───────────────────────┐ │
│  │ IngestRouter     │    │ WebSocket Router      │ │
│  │ POST /ingest     │    │ /ws/scada             │ │
│  └────────┬─────────┘    └──────────┬────────────┘ │
│           │                         │               │
│           ├─────────┬───────────────┤               │
│           │         │               │               │
│           ▼         ▼               ▼               │
│  ┌──────────────────────────────────────────────┐  │
│  │  RealtimeStateStore (Singleton)              │  │
│  │  - tags: {lagoon → {...}}                    │  │
│  │  - last_ts, pump_last_on, start_ts           │  │
│  └──────────────────────────────────────────────┘  │
│                      ↑                              │
│                      │                              │
│  ┌──────────────────────────────────────────────┐  │
│  │  IngestService                               │  │
│  │  - Bufferizado por minutos                   │  │
│  │  - Procesamiento de eventos                  │  │
│  │  - Detección ON/OFF                          │  │
│  └────────────┬─────────────────────────────────┘  │
│               │                                     │
│               │ (INSERT/UPDATE)                    │
│               ▼                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │  WebSocketManager (Singleton)                │  │
│  │  - Conexiones por laguna                     │  │
│  │  - Broadcast de ticks                        │  │
│  └──────────────────────────────────────────────┘  │
│               │                                     │
│               └─────────────┬──────────┬─────────   │
└────────────────────────────┼──────────┼───────────┘
                             │          │
                             ▼          ▼
                        ┌─────────────────┐
                        │   PostgreSQL    │
                        │                 │
                        │ ▪ scada_event   │
                        │ ▪ scada_minute  │
                        │ ▪ lagoons       │
                        └─────────────────┘
```

### Diagrama 2: Flujo de Ingest

```
POST /ingest/scada {lagoon, ts, tags}
    │
    ▼
┌──────────────────────────────────────┐
│ [1] Parsear payload                  │
│     - timestamp → ISO 8601 UTC       │
└─────────────┬────────────────────────┘
              │
              ▼
┌──────────────────────────────────────┐
│ [2] RealtimeStateStore.update()      │
│     - Actualizar tags                │
│     - Actualizar pump_last_on        │
│     - Detectar cambios bool          │
└─────────────┬────────────────────────┘
              │
              ▼
┌──────────────────────────────────────┐
│ [3] IngestService.ingest()           │
│     ├─ Bufferizar datos de minuto    │
│     ├─ Detectar cambios de evento    │
│     │  ├─ False→True: INSERT evento  │
│     │  └─ True→False: UPDATE evento  │
│     └─ Flush minutos cerrados        │
│        └─ INSERT/UPDATE ScadaMinute  │
└─────────────┬────────────────────────┘
              │
              ▼
         PostgreSQL COMMIT
              │
              ▼
┌──────────────────────────────────────┐
│ [4] WebSocketManager.broadcast()     │
│     - Enviar tick_payload a clientes │
└─────────────┬────────────────────────┘
              │
              ▼
        200 OK Response
```

### Diagrama 3: Evento Booleano Completo

```
Ingest #1: "bomba_1" = true (estado previo: false/null)
    │
    ├─ Detectar: False/null → True
    │
    └─ INSERT INTO scada_event
       ├─ id: <UUID>
       ├─ lagoon_id: "costa_del_lago"
       ├─ tag_id: "bomba_1"
       ├─ start_ts: 2026-02-09 14:30:45Z
       ├─ end_ts: NULL  ← 🔴 ABIERTO (ACTIVO)
       └─ created_at: NOW()

       _open_event_id[("costa_del_lago", "bomba_1")] = <id>

             Tiempo transcurrido...

Ingest #5: "bomba_1" = false (estado previo: true)
    │
    ├─ Detectar: True → False
    │
    └─ UPDATE scada_event
       WHERE id = _open_event_id[("costa_del_lago", "bomba_1")]
       SET end_ts = 2026-02-09 14:45:15Z  ← CERRADO

       Evento completo:
       ├─ Duración: 14:30:45 → 14:45:15 (≈14.5 min)
       └─ Estado final: Completado
```
---

### CORS

```python
# Configurado en main.py
allow_origins = [
  "http://192.168.1.22",
  "http://localhost:5173",  # Vite dev
  "http://localhost:3000",  # React dev
  "http://localhost:8080",
]
```

Agregar origins según necesidad.

---

## Referencias y Recursos

- **FastAPI Docs:** https://fastapi.tiangolo.com/
- **SQLAlchemy ORM:** https://docs.sqlalchemy.org/
- **WebSocket RFC 6455:** https://tools.ietf.org/html/rfc6455
- **ISO 8601 (Timestamps):** https://en.wikipedia.org/wiki/ISO_8601

---

## 🎓 Preguntas Frecuentes (FAQ)

### P1: ¿Por qué el timestamp va como string?

**R:** ISO 8601 es un estándar internacional y es agnóstico de zona horaria cuando incluye `Z` (UTC). El backend convierte a `datetime` de Python.

### P2: ¿Qué pasa si envío dos requests SIMULTÁNEAMENTE?

**R:** El `threading.Lock` en `IngestService` serializa el acceso. El segundo espera al primero.

### P3: ¿Puedo particionar scada_minute por tamaño?

**R:** Sí. PostgreSQL table partitioning by range (fecha) optimizaría queries históricas. Considerar para > 100M rows.

### P4: ¿El WebSocket es obligatorio para el frontend?

**R:** No. El frontend puede hacer polling a un endpoint REST `GET /scada/last` cada X segundos. Pero WebSocket es más eficiente.

### P5: ¿Cómo escalo a múltiples servidores?

**R:** 
- ❌ RealtimeStateStore + WebSocketManager son en-memory → necesita Redis/RabbitMQ
- ✅ IngestService + BD funcionan distribuidas
- Futura arquitectura: Queue centralizada + múltiples Workers

---

**Documento creado:** 2026-02-09  
**Autor:** Equipo de Desarrollo Crystal Lagoons  
**Versión:** 1.0
