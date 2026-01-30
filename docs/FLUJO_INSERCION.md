a# Arquitectura y flujo de inserción de datos (SCADA)

Este documento describe cómo la aplicación recibe datos SCADA, cómo se actualiza el estado en memoria, cómo se persisten datos en la BD y cómo se exponen REST/WS al frontend.

**Componentes principales**

- **API (FastAPI)**: routers en `app/routers` (p. ej. `ingest.py`, `scada_read.py`, `scada_ws.py`).
- **State store en memoria**: `app/state/store.py` (clase `RealtimeStateStore` / `StateStore`) mantiene valores por laguna, `last_ts`, `pump_last_on`, `end_ts`.
- **WebSocket manager**: `app/ws/manager.py` (clase `WebSocketManager`) gestiona conexiones por `lagoon_id` y broadcast.
- **Persistencia / worker**: `app/persist/worker.py` escribe snapshots periódicamente a DB; `app/persist/queue.py` define la cola si aplica.
- **Servicios de ingest**: `app/services/ingest_service.py` contiene lógica para ingest a nivel DB (eventos, flush minutos).
- **Repositorios/Modelos**: `app/repositories/*` y `app/models/*` (`ScadaMinute`, `ScadaEvent`) definen la persistencia física.
- **DB**: `app/db/session.py` con `SessionLocal` y `get_db()`.

**Formato de entrada (endpoint principal de ingest)**

- Endpoint: `POST /ingest/scada` (ver `app/routers/ingest.py`)
- Payload Pydantic: `IngestPayload` = { `lagoon_id`: str, `ts`: str | None, `tags`: dict }

Flujo de procesamiento (resumido)

1. Frontend / PLC envía POST a `/ingest/scada` con payload.
2. `ingest_scada` (router) extrae `lagoon_id`, `ts` (si no, usa UTC ahora) y `tags`.
3. Llama a `state.update(lagoon_id, tags, ts)` para actualizar estado en memoria:
   - actualiza `tags[lagoon_id]` con los últimos valores,
   - actualiza `last_ts[lagoon_id] = ts`,
   - si hay booleans (bombas), actualiza `pump_last_on` y `end_ts` según flancos.
4. Tras actualizar el estado en memoria, el router hace `ws.broadcast(lagoon_id, await state.tick_payload(lagoon_id))` para notificar a todos los clientes WS conectados a esa laguna.
5. `ingest_scada` responde con {"ok": True} inmediatamente (latencia baja para el emisor).

Observaciones sobre persistencia en BD

- La ruta de ingest HTTP no escribe la BD directamente en `ingest_scada`; en cambio mantiene el estado en memoria y notifica WS.
- Hay dos mecanismos para persistir:
  - `app/services/ingest_service.py` (`ingest`) — lógica que maneja eventos (abrir/cerrar eventos booleanos) y hace flush por minuto usando INSERT ... ON CONFLICT para `scada_minute`. Esta función requiere un `db: Session` y se usa cuando deseas procesar e insertar desde un worker o pipeline que tenga acceso a la DB.
  - `app/persist/worker.py` — `PersistWorker` itera periódicamente (cada 60s) sobre `state.tags` y llama a `ScadaMinuteRepository.insert_snapshot(...)` para persistir snapshots actuales por laguna.
- Modelos clave en BD:
  - `ScadaMinute` (tabla `scada_minute`): (lagoon_id, tag_id, bucket_ts) con `uq_scada_minute` y columnas `value_num`, `value_bool`, `updated_at`.
  - `ScadaEvent` (tabla `scada_event`): registros de eventos booleanos con `start_ts` y `end_ts`, index para abiertos.

Flujo de persistencia temporal / agregado

- Lógica de agregación por minuto en `ingest_service.ingest`:
  - Bufferiza valores por `(lagoon_id, bucket_minuto)` en memoria.
  - Detecta flancos para valores booleanos y crea/actualiza `ScadaEvent` (open/close).
  - Al cerrar minutos (cuando llega un timestamp mayor), realiza `INSERT ... ON CONFLICT` para cada `tag` en `scada_minute` y hace `db.commit()`.
- Alternativa: el `PersistWorker` guarda snapshots regulares usando el repositorio `ScadaMinuteRepository`.

WebSocket (cómo el frontend recibe datos)

- Endpoint WS: `ws://<host>/ws/scada/{lagoon_id}` (ver `app/routers/scada_ws.py`).
- Conexión:
  - El cliente abre el WebSocket y el servidor acepta y registra la conexión con `manager.connect(lagoon_id, ws)`.
  - Si hay snapshot en `state`, el servidor envía un mensaje inicial `{ "type": "snapshot", "lagoon_id": ..., "ts": ..., "tags": {...} }`.
  - Después, el servidor envía mensajes de tipo `tick` cuando llega un `ingest` que ejecuta `ws.broadcast(...)`.
- Formato de mensajes: al menos `snapshot` y `tick` con campos `lagoon_id`, `ts`, `tags`, `pump_last_on`, `end_ts`.

REST para lectura

- Endpoints en `app/routers/scada_read.py`:
  - `GET /scada/{lagoon_id}/last-minute` → usa `scada_read_service.get_last_minute` → devuelve snapshot del último bucket en BD.
  - `GET /scada/{lagoon_id}/current` → usa `get_current` → devuelve estado actual basado en últimas filas por tag en `scada_minute`.
- Ambos endpoints dependen de `get_db()` para obtener `Session` y usan repositorios (`ScadaReadRepository`).

Recomendaciones y notas de diseño

- Latencia: la ruta `POST /ingest/scada` es rápida porque solo actualiza memoria y notifica WS; la persistencia se delega a workers/servicios.
- Consistencia eventual: como la escritura en BD puede ser asíncrona (worker o servicio), el frontend debe confiar en WS para datos en tiempo real y en REST/BD para consultas históricas/confirmadas.
- Escalabilidad: `WebSocketManager` mantiene conexiones en memoria por proceso. Para múltiples instancias, necesitarás un broker pub/sub (Redis) para broadcast entre procesos.
- Idempotencia y deduplicación: el `ingest_service.ingest` y `ScadaMinute` usan `ON CONFLICT` para evitar duplicados por `(lagoon_id, tag_id, bucket_ts)`.

Pasos siguientes sugeridos

- Agregar un worker que invoque `ingest_service.ingest` con una cola si se desea persistencia inmediata y determinista.
- Añadir pruebas unitarias para `ingest_service.ingest` y `PersistWorker`.
- Dibujar un diagrama de secuencia (cliente → API → State → WS → Persist) y un diagrama de despliegue si es necesario.

---

Archivo(s) de referencia principales:
- `app/routers/ingest.py`
- `app/state/store.py`
- `app/ws/manager.py`
- `app/services/ingest_service.py`
- `app/persist/worker.py`
- `app/models/scada_minute.py`, `app/models/scada_event.py`
- `app/repositories/scada_read_repository.py`

