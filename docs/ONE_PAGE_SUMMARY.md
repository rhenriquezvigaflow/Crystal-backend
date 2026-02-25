# 🎯 One-Page Summary - Crystal Lagoons Backend

**Resumen completo en 1 pagina**

**Version doc:** 1.1 | **Actualizado:** 2026-02-25

---

## 🏗️ ARQUITECTURA EN 30 SEGUNDOS

```
SCADA Device → POST /ingest/scada → FastAPI
                                        ↓
                     ┌─────────────────────────────┼─────────────────────────────┐
                     ↓                             ↓                             ↓
           RealtimeStateStore          IngestService                WebSocketManager
           (Estado en memoria)         (Lógica BD)                  (Real-time)
                     │                             │                             │
                     ├─ Timezone Loader + Watchdog                        │
                     │                             │                             │
                     └─────────────────────────────┼─────────────────────────────┘
                                        ↓
                              PostgreSQL Database
                              • scada_event (eventos)
                              • scada_minute (histórico)
```

---

## 🔄 FLUJO DE DATOS: 5 PASOS

```
1. POST /ingest/scada {lagoon, ts, tags}
           ↓
2. Actualizar RealtimeStateStore (memoria)
           ↓
3. Buffering + Eventos + Persistencia → BD
           ↓
4. Broadcast WebSocket → Clientes
           ↓
5. Respuesta HTTP 200 {ok: true}
```

**Tiempo total:** ~50-200ms

---

## 📡 3 INTERFACES

| Interfaz | URL | Método | Uso |
|----------|-----|--------|-----|
| **HTTP** | POST /ingest/scada | POST | Enviar datos |
| **HTTP** | GET /scada/{lagoon_id}/current | GET | Leer estado en memoria |
| **HTTP** | GET /scada/{lagoon_id}/last-minute | GET | Valores por minuto |
| **HTTP** | GET /scada/history/{resolution} | GET | Consultar historico agregado |
| **HTTP** | GET /scada/{lagoon_id}/pump-events/last-3 | GET | Ultimos 3 eventos de bombas |
| **WebSocket** | ws://host:8000/ws/scada?lagoon_id={lagoon_id} | WS | Real-time |

---

## 📦 PAYLOAD ESTÁNDAR

**Entrada:**
```json
{
  "lagoon_id": "laguna_1",
  "ts": "2026-02-09T14:30:45Z",  // Opcional
  "tags": {
    "bomba": true,
    "temperatura": 28.5
  }
}
```

**Salida WebSocket:**
```json
{
  "type": "tick",
  "lagoon_id": "laguna_1",
  "ts": "2026-02-09T14:30:45Z",
  "tags": {"bomba": true, "temperatura": 28.5},
  "pump_last_on": {"bomba": "2026-02-09T14:30:45Z"},
  "start_ts": {"laguna_1": "2026-02-09T14:30:45Z"}
}
```

---

## 💾 BASES DE DATOS

### ScadaEvent (Eventos)
| Campo | Tipo | Uso |
|-------|------|-----|
| id | UUID | Identificador único |
| lagoon_id | VARCHAR | ¿Cuál laguna? |
| tag_id | VARCHAR | ¿Cuál sensor? |
| start_ts | TIMESTAMP | Cuándo encendió |
| end_ts | TIMESTAMP | Cuándo apagó (NULL = activo) |

**Uso:** Detectar ON/OFF de bombas

### ScadaMinute (Histórico)
| Campo | Tipo | Uso |
|-------|------|-----|
| id | BIGINT | Auto-increment |
| lagoon_id | VARCHAR | ¿Cuál laguna? |
| tag_id | VARCHAR | ¿Cuál sensor? |
| bucket | TIMESTAMP | Minuto truncado (14:30:00Z) |
| value_num | FLOAT | Valor numérico (temperatura, presión) |
| value_bool | BOOLEAN | Valor booleano (ON/OFF) |

**Uso:** Serie temporal por minuto

---

## 🧩 COMPONENTES

| Componente | Archivo | Responsabilidad |
|-----------|---------|-----------------|
| FastAPI App | main.py | Inicialización, singletons, routers |
| Ingest Router | routers/ingest.py | Endpoint POST /ingest/scada |
| Ingest Service | services/ingest_service.py | **CORE**: Buffer, eventos, BD |
| WebSocket Manager | ws/manager.py | Manager conexiones bidireccionales |
| RealtimeStateStore | state/store.py | Cache en memoria del último estado |
| Persist Worker | persist/worker.py | [Futuro] Persistencia asincrónica |

---

## 🔐 THREAD-SAFETY

✅ **RealtimeStateStore** - `async/await`  
✅ **IngestService** - `threading.Lock`  
✅ **WebSocketManager** - `asyncio.Lock`  

→ Seguro para concurrencia

---

## 📊 EVENTO BOOLEANO

```
INGEST: bomba = true (prev: false)
    ↓
INSERT scada_event (start_ts, end_ts=NULL)
    │ ABIERTO (activo)
    
⏱️ 15 minutos después...
    │
INGEST: bomba = false (prev: true)
    ↓
UPDATE scada_event SET end_ts = NOW()
    │ CERRADO (completado)
    
RESULTADO: Evento de 15 minutos registrado
```

---

## 🚀 COMANDOS ÚTILES

```bash
# Iniciar servidor
python -m uvicorn app.main:app --reload

# Enviar dato
curl -X POST http://localhost:8000/ingest/scada \
  -d '{"lagoon_id":"test","tags":{"t":28.5}}'

# Conectar WebSocket
wscat -c "ws://localhost:8000/ws/scada?lagoon_id=test"

# Ver estado BD
psql -c "SELECT * FROM scada_minute WHERE lagoon_id='test';"

# Ver eventos abiertos
psql -c "SELECT * FROM scada_event WHERE end_ts IS NULL;"

# Tests
pytest tests/ -v
```

---

## 🐛 TROUBLESHOOTING RÁPIDO

| Problema | Solución |
|----------|----------|
| `Connection refused` | `psql -c "SELECT 1"` - verificar PostgreSQL |
| `404 /ingest/scada` | Verificar que app está corriendo |
| `WebSocket fail` | Verificar CORS en main.py |
| `No se guardan datos` | Verificar `db.commit()` |
| Datos lentos | Verificar índices en BD, pool conexiones |

---

## 📁 ESTRUCTURA CLAVE

```
app/
├─ main.py                      ← Punto de entrada
├─ routers/ingest.py            ← POST /ingest/scada
├─ services/ingest_service.py   ← CORE lógica
├─ ws/manager.py                ← WebSocket
├─ state/store.py               ← Estado en memoria
├─ models/
│  ├─ scada_event.py
│  └─ scada_minute.py
└─ db/session.py                ← Conexión BD
```

---

## 📈 RENDIMIENTO

| Métrica | Recomendación |
|---------|---|
| Ingest rate | 1-100 msg/sec ✅ |
| Lagunas simultáneas | 10-20 ✅ |
| Clientes WS | 50-100 ✅ / 100-500 ⚠️ |
| Buffer máx | 200,000 mensajes |
| Índices | CRÍTICOS para >1M rows |

---

## 🎯 EXTENSIONES COMUNES

**Agregar nuevo sensor:**
```python
# En el cliente SCADA:
POST /ingest/scada
{
  "lagoon_id": "laguna_1",
  "tags": {
    "nuevo_sensor": 42.5  ← ¡Automático!
  }
}
# Se guarda en BD, se envía por WS → ¡Hecho!
```

**Agregar nuevo endpoint:**
```python
# app/routers/mi_router.py
@router.get("/mi_endpoint/{lagoon_id}")
async def get_data(lagoon_id: str, request):
    state = request.app.state.state_store
    return state.tags.get(lagoon_id, {})

# En main.py:
app.include_router(mi_router)
```

**Agregar validación:**
```python
# app/schemas/scada.py
class IngestPayload(BaseModel):
    lagoon_id: str
    tags: dict
    
    @validator('lagoon_id')
    def lagoon_id_min_length(cls, v):
        if len(v) < 3:
            raise ValueError('Min 3 caracteres')
        return v
```

---

## ✅ CHECKLIST DEPLOY

- [ ] PostgreSQL corriendo
- [ ] `.env` con `DATABASE_URL`
- [ ] `pip install -r requirements.txt`
- [ ] `curl http://localhost:8000/health` → OK
- [ ] `POST /ingest/scada` → responde
- [ ] WebSocket conecta
- [ ] Datos aparecen en BD
- [ ] Tests pasan

---

## 📚 DOCUMENTACIÓN COMPLETA

| Doc | Tiempo | Detalle |
|-----|--------|---------|
| [ARQUITECTURA_Y_FLUJO.md](./ARQUITECTURA_Y_FLUJO.md) | 20-30 min | Arquitectura completa |
| [GUIA_TECNICA_DESARROLLO.md](./GUIA_TECNICA_DESARROLLO.md) | 45-60 min | Guía con código |
| [DIAGRAMAS_FLUJOS.md](./DIAGRAMAS_FLUJOS.md) | 15-20 min | Diagramas ASCII |
| [INDEX.md](./INDEX.md) | 10 min | Mapa de navegación |

👉 **Comienza en:** [INDEX.md](./INDEX.md)

---

## 🔗 ATAJOS ÚTILES

```python
# Acceder a los singletons
state = request.app.state.state_store
ws_manager = request.app.state.ws_manager

# Query típica
db = SessionLocal()
row = db.query(ScadaMinute).filter(...).first()
db.close()

# Actualizar estado
await state.update(lagoon_id, tags, ts_iso)

# Broadcast
await ws_manager.broadcast(lagoon_id, mensaje)
```

---

## 🎓 "AL MENOS DEBES SABER"

1. **HTTP POST** → `POST /ingest/scada` con `{lagoon_id, tags}`
2. **WebSocket** → `ws://host:8000/ws/scada?lagoon_id=X` para real-time
3. **BD** → `scada_event` (eventos) + `scada_minute` (histórico)
4. **Flujo** → Ingest → Buffer → BD → Broadcast
5. **Thread-safe** → Usa Locks, no hay race conditions
6. **Escalable** → 10-20 lagunas sin problemas
7. **Eventos** → `start_ts` ON, UPDATE con `end_ts` cuando OFF

---

## Novedades v1.1 (2026-02-25)

1. Endpoint nuevo para frontend:
   - `GET /scada/{lagoon_id}/pump-events/last-3`
2. Repositorio de eventos alineado con vista:
   - `vw_scada_last_3_pump_actions` + filtro por `lagoon_id`
3. Historico con vistas continuas documentado:
   - script `scripts/sql/create_scada_continuous_aggregates.sql`
4. Resolucion historica por path:
   - `GET /scada/history/{resolution}`
5. WebSocket activo documentado:
   - `ws://host:8000/ws/scada?lagoon_id={lagoon_id}`

---

<div align="center">

**¿Preguntas?** → Ver documentación completa  
**¿Necesitas debuggear?** → revisar las secciones de troubleshooting en [ARQUITECTURA_Y_FLUJO.md](./ARQUITECTURA_Y_FLUJO.md#-endpoints-http) o [GUIA_TECNICA_DESARROLLO.md#-troubleshooting]  
**¿Quieres entender más?** → [ARQUITECTURA_Y_FLUJO.md](./ARQUITECTURA_Y_FLUJO.md)  


</div>

---
Ultima actualizacion: 2026-02-25
