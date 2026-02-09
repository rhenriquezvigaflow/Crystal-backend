# 💻 Guía Técnica de Desarrollo - Crystal Lagoons Backend

**Última actualización:** Febrero 2026  
**Público:** Desarrolladores Python/FastAPI

---

## 📖 Tabla de Contenidos

1. [Setup y Ejecución](#setup-y-ejecución)
2. [Estructura del Código](#estructura-del-código)
3. [Ejemplos Prácticos](#ejemplos-prácticos)
4. [Testing](#testing)
5. [Debugging](#debugging)
6. [Extensiones Comunes](#extensiones-comunes)
7. [Troubleshooting](#troubleshooting)

---

## 🚀 Setup y Ejecución

### Requisitos

```bash
Python 3.10+
PostgreSQL 14+
pip (o poetry)
```

### Instalación

```bash
# 1. Clonar repositorio
cd crystal-backend

# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate  # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Variables de entorno (.env)
DATABASE_URL=postgresql://user:pass@localhost/crystal
DEBUG=True
```

### Ejecutar la Aplicación

**Opción 1: Script oficial**
```bash
# Windows
start.bat

# Linux/Mac
chmod +x start.sh && ./start.sh
```

**Opción 2: Uvicorn directo**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Opción 3: Python**
```bash
python -m uvicorn app.main:app --reload
```

### Verificar que funciona

```bash
curl http://localhost:8000/health
# Respuesta: {"status": "ok"}
```

---

## 🗂️ Estructura del Código

```
app/
├── main.py                    # 🔴 Punto de entrada
├── core/
│   ├── config.py             # Configuración y variables
│   └── logging.py            # Logger personalizado
├── db/
│   ├── session.py            # 🔴 Conexión a PostgreSQL
│   └── __init__.py
├── models/                    # 🔴 ORM Models (SQLAlchemy)
│   ├── base.py               # Declarative base
│   ├── scada_event.py        # Modelo de eventos
│   ├── scada_minute.py       # Modelo de agregados
│   └── __init__.py
├── schemas/                   # Pydantic models (validación)
│   └── scada.py
├── repositories/              # Acceso a datos
│   └── scada_event_repository.py
├── services/                  # 🔴 Lógica de negocio
│   └── ingest_service.py
├── routers/                   # 🔴 Endpoints HTTP
│   ├── ingest.py
│   └── health.py
├── ws/                        # 🔴 WebSocket
│   ├── manager.py
│   └── routes.py
├── persist/                   # Persistencia (worker)
│   ├── worker.py
│   └── queue.py
├── state/                     # 🔴 Estado en memoria
│   └── store.py
├── scada/
│   └── history/              # Historial SCADA
│       └── router.py
└── __pycache__/
```

**Archivos críticos** (marcados 🔴):
- `main.py` - Inicialización
- `db/session.py` - BD
- `models/` - Esquemas
- `services/ingest_service.py` - Core
- `routers/ingest.py` - API
- `ws/` - WebSocket
- `state/store.py` - Estado

---

## Ejemplos Prácticos

### Ejemplo 1: Entender el Flujo Completo

**Archivo:** `app/services/ingest_service.py`

```python
def ingest(lagoon_id: str, ts: datetime, tags: dict, db: Session):
    """
    Procesia un tick SCADA:
    1. Bufferiza datos
    2. Detecta eventos
    3. Persistirá datos cerrados
    """
    
    ts_utc = _to_utc(ts)                           # ← Normalizar a UTC
    bucket = _bucket_minute(ts_utc)                # ← Truncar a minuto
    
    with _lock:                                     # ← THREAD SAFE
        key = (lagoon_id, bucket)
        _minute_buffer.setdefault(key, {})         # ← Crear bucket si no existe
        
        # PROCESAR cada tag
        for tag_id, value in tags.items():
            # Agregar a lista de este minuto
            _minute_buffer[key].setdefault(tag_id, []).append(value)
            
            # Si es booleano, detectar cambio
            if isinstance(value, bool):
                prev = _last_bool_state.get((lagoon_id, tag_id))
                
                # Transición OFF → ON
                if prev in (False, None) and value is True:
                    ev = ScadaEvent(
                        lagoon_id=lagoon_id,
                        tag_id=tag_id,
                        start_ts=ts_utc,
                    )
                    db.add(ev)
                    db.flush()                      # ← Obtener ID generado
                    _open_event_id[(lagoon_id, tag_id)] = ev.id
                
                # Transición ON → OFF
                elif prev is True and value is False:
                    ev_id = _open_event_id.pop((lagoon_id, tag_id), None)
                    if ev_id:
                        db.query(ScadaEvent).filter(
                            ScadaEvent.id == ev_id
                        ).update({"end_ts": ts_utc})
                
                _last_bool_state[(lagoon_id, tag_id)] = value
        
        db.commit()  # ← Persistir eventos
        
        # FLUSH minutos PASADOS (ya cerrados)
        flush_keys = [
            k for k in list(_minute_buffer.keys())
            if k[0] == lagoon_id and k[1] < bucket  # ← Minutos anteriores
        ]
        
        for fk in flush_keys:
            lagoon_id_fk, bucket_key = fk
            tag_dict = _minute_buffer.pop(fk, {})
            
            # Por cada tag, guardar último valor
            for tag_id, values in tag_dict.items():
                last_val = values[-1]               # ← ÚLTIMO valor del minuto
                
                # Insertar/Actualizar ScadaMinute
                stmt = insert(ScadaMinute).values(
                    lagoon_id=lagoon_id_fk,
                    tag_id=tag_id,
                    bucket=bucket_key,
                    value_num=float(last_val) if isinstance(last_val, (int, float)) else None,
                    value_bool=last_val if isinstance(last_val, bool) else None,
                )
                
                # Si ya existe, actualizar
                stmt = stmt.on_conflict_do_update(
                    index_elements=["lagoon_id", "tag_id", "bucket"],
                    set_={
                        "value_num": stmt.excluded.value_num,
                        "value_bool": stmt.excluded.value_bool,
                        "updated_at": stmt.excluded.updated_at,
                    },
                )
                
                db.execute(stmt)
        
        if flush_keys:
            db.commit()
```

**Key Concepts:**
- `_lock` - Sincronización (thread-safe)
- `_bucket_minute()` - Agrupar por minuto
- `_last_bool_state` - Detectar cambios
- `db.flush()` - Obtener IDs sin commit
- `db.commit()` - Persistir a BD

---

### Ejemplo 2: Cliente HTTP (cURL)

**Enviar datos SCADA:**

```bash
# ✅ Request válido
curl -X POST http://localhost:8000/ingest/scada \
  -H "Content-Type: application/json" \
  -d '{
    "lagoon_id": "laguna_1",
    "ts": "2026-02-09T14:30:45.123Z",
    "tags": {
      "bomba_principal": true,
      "temperatura_agua": 28.5,
      "ph_nivel": 7.2,
      "oxigeno": true
    }
  }'

# ✅ Sin timestamp (usa NOW())
curl -X POST http://localhost:8000/ingest/scada \
  -H "Content-Type: application/json" \
  -d '{
    "lagoon_id": "laguna_1",
    "tags": {"bomba_principal": false}
  }'

# ❌ Inválido (falta lagoon_id)
curl -X POST http://localhost:8000/ingest/scada \
  -H "Content-Type: application/json" \
  -d '{"tags": {"temperatura": 28.5}}'
# Error 422: Unprocessable Entity
```

---

### Ejemplo 3: Cliente WebSocket (JavaScript/Node)

**Conectarse y recibir datos:**

```javascript
// 📁 frontend.js

const lagoonId = "laguna_1";
const ws = new WebSocket(`ws://localhost:8000/ws/scada?lagoon_id=${lagoonId}`);

// Abierto
ws.onopen = () => {
  console.log("✅ WebSocket conectado");
};

// Mensaje recibido
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  console.log(`[${data.type}]`, data);
  
  if (data.type === "snapshot") {
    // Inicializar UI con datos existentes
    updateUI(data);
  } else if (data.type === "tick") {
    // Actualizar UI en tiempo real
    updateUIRealtime(data);
  }
};

// Error
ws.onerror = (event) => {
  console.error("❌ Error WebSocket:", event);
};

// Cierre
ws.onclose = () => {
  console.log("⚠️ WebSocket desconectado");
  // Reconectar después de 3 segundos
  setTimeout(() => location.reload(), 3000);
};

// Función para actualizar UI
function updateUI(data) {
  document.getElementById("lastUpdate").textContent = data.ts;
  document.getElementById("temperature").textContent = data.tags.temperatura_agua;
  document.getElementById("pumpStatus").textContent = 
    data.tags.bomba_principal ? "ON" : "OFF";
}

function updateUIRealtime(data) {
  // Igual a updateUI pero con animaciones
  updateUI(data);
  document.getElementById("indicator").classList.add("pulse");
}
```

**Python (usando `websockets`):**

```python
import asyncio
import websockets
import json

async def connect_to_scada():
    uri = "ws://localhost:8000/ws/scada?lagoon_id=laguna_1"
    
    async with websockets.connect(uri) as websocket:
        # Recibir snapshot inicial
        snapshot = json.loads(await websocket.recv())
        print(f"Snapshot: {snapshot}")
        
        # Recibir ticks en vivo
        async for message in websocket:
            tick = json.loads(message)
            print(f"Tick: {tick['tags']}")

# Ejecutar
asyncio.run(connect_to_scada())
```

---

### Ejemplo 4: Interactuar con Estado (AVANZADO)

**Leer estado en tiempo real:**

```python
# 📁 app/routers/custom.py (nuevo)

from fastapi import APIRouter
from app.state.store import RealtimeStateStore

router = APIRouter()

@router.get("/state/{lagoon_id}")
async def get_current_state(lagoon_id: str, request):
    """Endpoint para verificar estado actual en memoria"""
    state: RealtimeStateStore = request.app.state.state_store
    
    return {
        "lagoon_id": lagoon_id,
        "tags": state.tags.get(lagoon_id, {}),
        "last_ts": state.last_ts.get(lagoon_id),
        "pump_last_on": state.pump_last_on.get(lagoon_id, {}),
        "start_ts": state.start_ts.get(lagoon_id),
    }

# En main.py, agregar:
# app.include_router(custom_router)
```

**Test:**
```bash
curl http://localhost:8000/state/laguna_1
```

---

### Ejemplo 5: Query Historial Desde BD

**Obtener datos de un día:**

```python
# 📁 app/routers/history.py

from datetime import datetime, timedelta, timezone
from sqlalchemy import and_

@router.get("/history/{lagoon_id}")
async def get_history(
    lagoon_id: str,
    days: int = 1,
    request: Request,
):
    """Obtener histórico de últimos N días"""
    db = SessionLocal()
    try:
        # Calcular rango de fechas
        now = datetime.now(timezone.utc)
        start_date = now - timedelta(days=days)
        
        # Query a BD
        rows = db.query(ScadaMinute).filter(
            and_(
                ScadaMinute.lagoon_id == lagoon_id,
                ScadaMinute.bucket >= start_date,
                ScadaMinute.bucket <= now,
            )
        ).order_by(ScadaMinute.bucket.desc()).all()
        
        # Agrupar por tag
        result = {}
        for row in rows:
            if row.tag_id not in result:
                result[row.tag_id] = []
            
            result[row.tag_id].append({
                "bucket": row.bucket.isoformat(),
                "value": row.value_num or row.value_bool,
            })
        
        return result
    
    finally:
        db.close()
```

---

## ✅ Testing

### Unit Testing

**Archivo:** `tests/test_ingest_service.py`

```python
import pytest
from datetime import datetime, timezone
from app.services.ingest_service import ingest, _bucket_minute, _to_utc
from app.db.session import SessionLocal
from app.models.scada_event import ScadaEvent
from app.models.scada_minute import ScadaMinute

class TestBucketMinute:
    def test_bucket_truncates_to_minute(self):
        ts = datetime(2026, 2, 9, 14, 30, 45, 123456, tzinfo=timezone.utc)
        bucket = _bucket_minute(ts)
        
        assert bucket.second == 0
        assert bucket.microsecond == 0
        assert bucket.hour == 14
        assert bucket.minute == 30

class TestIngestService:
    def test_ingest_numeric_value(self):
        """Test guardar valor numérico"""
        db = SessionLocal()
        
        ingest(
            lagoon_id="test_lagoon",
            ts=datetime.now(timezone.utc),
            tags={"temperatura": 28.5},
            db=db,
        )
        
        # Verificar que ScadaMinute fue creado
        minute = db.query(ScadaMinute).filter(
            ScadaMinute.tag_id == "temperatura"
        ).first()
        
        assert minute is not None
        assert minute.value_num == 28.5
        
        db.close()
    
    def test_ingest_boolean_creates_event(self):
        """Test evento ON/OFF"""
        db = SessionLocal()
        
        # Ingest 1: bomba OFF → ON
        ingest(
            lagoon_id="test_lagoon",
            ts=datetime.now(timezone.utc),
            tags={"bomba": True},
            db=db,
        )
        
        # Verificar evento abierto
        event = db.query(ScadaEvent).filter(
            ScadaEvent.tag_id == "bomba"
        ).first()
        
        assert event is not None
        assert event.end_ts is None  # Abierto
        
        db.close()

# Ejecutar tests
# pytest tests/test_ingest_service.py -v
```

### Integration Testing

**Archivo:** `tests/test_api.py`

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

class TestIngestAPI:
    def test_ingest_scada_success(self):
        """Test endpoint POST /ingest/scada"""
        response = client.post("/ingest/scada", json={
            "lagoon_id": "test",
            "tags": {"temp": 28.5}
        })
        
        assert response.status_code == 200
        assert response.json() == {"ok": True}
    
    def test_ingest_scada_invalid_payload(self):
        """Test payload inválido"""
        response = client.post("/ingest/scada", json={
            "tags": {"temp": 28.5}  # Falta lagoon_id
        })
        
        assert response.status_code == 422
    
    def test_health_check(self):
        """Test endpoint /health"""
        response = client.get("/health")
        
        assert response.status_code == 200

# Ejecutar: pytest tests/test_api.py -v
```

---

## 🐛 Debugging

### 1. Logs

**Ver logs de nivel DEBUG:**

```bash
# Terminal 1: Ejecutar app con DEBUG
DEBUG=True python -m uvicorn app.main:app --reload

# Terminal 2: Ver logs específicos
tail -f logs/app.log | grep "INGEST"
```

**Python code:**

```python
from app.core.logging import get_logger

logger = get_logger("mi_modulo")

logger.debug("Valor debug:", valor)    # No aparece en prod
logger.info("Información:", info)       # Aparece siempre
logger.warning("Advertencia!")          # Amarillo
logger.error("Error:", exc_info=True)   # Rojo
```

### 2. SQL Debugging

**Ver queries SQL que ejecuta:**

```python
# En app/db/session.py
import logging

logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)  # Ver SQL

# Luego verás todas las queries en la terminal
```

### 3. Inspeccionar Estado

**Breakpoint en código:**

```python
# app/routers/ingest.py

@router.post("/ingest/scada")
async def ingest_scada(payload: IngestPayload, request: Request):
    # ... código ...
    
    # Aquí agregar breakpoint
    import pdb; pdb.set_trace()
    
    state = request.app.state.state_store
    # Ahora en consola: print(state.tags)
```

**O usar VS Code debugger:**

```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app.main:app", "--reload"],
      "jinja": true
    }
  ]
}
```

### 4. Verificar BD

**PostgreSQL CLI:**

```bash
# Conectarse
psql -U user -d crystal -h localhost

# Ver últimos eventos
SELECT id, lagoon_id, tag_id, start_ts, end_ts 
FROM scada_event 
ORDER BY created_at DESC 
LIMIT 10;

# Ver últimos minutos
SELECT lagoon_id, tag_id, bucket, value_num, value_bool 
FROM scada_minute 
WHERE lagoon_id = 'costa_del_lago'
ORDER BY bucket DESC 
LIMIT 20;

# Contar eventos abiertos (bomba activa)
SELECT count(*) FROM scada_event 
WHERE end_ts IS NULL 
AND lagoon_id = 'costa_del_lago';
```

---

## 🔧 Extensiones Comunes

### Agregar Nuevo Endpoint

**1. Crear ruta:**

```python
# app/routers/stats.py
from fastapi import APIRouter

router = APIRouter(prefix="/stats", tags=["statistics"])

@router.get("/{lagoon_id}/uptime")
async def get_uptime(lagoon_id: str, request):
    """Calcular uptime de bomba"""
    db = SessionLocal()
    try:
        # Lógica...
        return {"uptime_hours": 14.5}
    finally:
        db.close()
```

**2. Registrar en main.py:**

```python
from app.routers.stats import router as stats_router

app.include_router(stats_router)

# Ahora disponible: GET /stats/laguna_1/uptime
```

---

### Agregar Nuevo Modelo de BD

**1. Crear modelo:**

```python
# app/models/scada_alert.py
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, func
from app.models.base import Base

class ScadaAlert(Base):
    __tablename__ = "scada_alert"
    
    id = Column(String, primary_key=True, server_default=func.gen_random_uuid())
    lagoon_id = Column(String(64), ForeignKey("lagoons.id"), nullable=False)
    tag_id = Column(String(64), nullable=False)
    alert_type = Column(String(32), nullable=False)  # "high_temp", "low_oxygen"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

**2. Crear migración:**

```bash
# Con Alembic (si lo usan)
alembic revision --autogenerate -m "Add scada_alert table"
alembic upgrade head
```

**3. Usar en código:**

```python
from app.models.scada_alert import ScadaAlert

# En ingest_service.py
if value > TEMP_THRESHOLD:
    alert = ScadaAlert(
        lagoon_id=lagoon_id,
        tag_id=tag_id,
        alert_type="high_temp"
    )
    db.add(alert)
    db.commit()
```

---

### Agregar Validación Personalizada

**1. Crear validator Pydantic:**

```python
# app/schemas/scada.py
from pydantic import BaseModel, validator

class IngestPayload(BaseModel):
    lagoon_id: str
    ts: str | None = None
    tags: dict
    
    @validator('lagoon_id')
    def validate_lagoon_id(cls, v):
        if not v or len(v) < 3:
            raise ValueError('lagoon_id debe tener al menos 3 caracteres')
        return v.lower()
    
    @validator('tags')
    def validate_tags(cls, v):
        if not v:
            raise ValueError('tags no puede estar vacío')
        return v
```

**2. Se valida automáticamente:**

```bash
curl -X POST http://localhost:8000/ingest/scada \
  -d '{"lagoon_id": "xx", "tags": {}}'
# Error 422 - ValidationError
```

---

## 🆘 Troubleshooting

### Problema 1: "No module named 'app'"

**Causa:** Ruta incorrecta

**Solución:**
```bash
cd crystal-backend  # Estar en la carpeta correcta
# O agregar al PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

---

### Problema 2: Connection refused (PostgreSQL)

**Causa:** BD desconectada

**Solución:**
```bash
# Verificar que PostgreSQL está corriendo
psql -h localhost -U user -c "SELECT 1"

# O verificar en .env la DATABASE_URL:
# DATABASE_URL=postgresql://user:password@localhost:5432/crystal
```

---

### Problema 3: WebSocket connection error

**Causa:** Navegador → Servidor tiene CORS issue

**Solución:** Verificar `app/main.py`

```python
CORSMiddleware(
    allow_origins=["http://localhost:5173"],  # Agregar origin
    allow_credentials=True,
)
```

---

### Problema 4: "Event loop closed" o "RuntimeError"

**Causa:** Asyncio issue (threading)

**Solución:** No mezclar `async/await` con threading

```python
# ❌ MAL
async def my_func():
    threading.Thread(target=sync_func).start()

# ✅ BIEN
async def my_func():
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, sync_func)
```

---

### Problema 5: Datos no se guardaban en BD

**Causa:** Falta `db.commit()`

**Solución:**
```python
db.add(record)
db.flush()  # Obtener ID
db.commit() # ← OBLIGATORIO
```

---

## 📞 Soporte

Para preguntas o issues:
1. Revisar este documento
2. Buscar en repositorio (git log -p --all -S "keyword")
3. Consultar con equipo lead

---

**Actualizado:** 2026-02-09
