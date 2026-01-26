# Arquitectura - Crystal Lagoons SCADA Backend

## 📋 Descripción General

El backend de Crystal Lagoons es una API construida con **FastAPI** que ingiere y procesa datos de telemetría (SCADA) desde múltiples lagunas. El sistema está diseñado para:

- Recibir datos de sensores desde sistemas SCADA (Rockwell, Siemens, etc.)
- Almacenar datos en minutas agregadas
- Rastrear eventos booleanos con timestamps de inicio/fin
- Usar PostgreSQL como base de datos principal
- Transmitir datos en tiempo real mediante WebSocket
- Garantizar persistencia confiable de datos mediante cola de trabajos

---

## 🏗️ Estructura del Proyecto

```
crystal-backend/
├── app/
│   ├── main.py                 # Punto de entrada de la aplicación FastAPI
│   ├── core/
│   │   ├── config.py          # Configuración (settings) de la aplicación
│   │   └── logging.py         # Setup de logging
│   ├── db/
│   │   └── session.py         # Sesiones y conexión a base de datos
│   ├── models/
│   │   ├── base.py            # Clase base SQLAlchemy (DeclarativeBase)
│   │   ├── lagoon.py          # Modelo de Laguna
│   │   ├── scada_event.py     # Modelo de Eventos SCADA (booleanos)
│   │   └── scada_minute.py    # Modelo de Datos SCADA Agregados por Minuto
│   ├── routers/
│   │   ├── health.py          # Router de health check
│   │   ├── ingest.py          # Router de ingesta de datos SCADA
│   │   ├── scada_read.py      # Router de lectura de datos SCADA
│   │   └── scada_ws.py        # Router de WebSocket para SCADA
│   ├── schemas/
│   │   ├── ingest.py          # Schemas Pydantic para ingesta
│   │   └── scada.py           # Schemas Pydantic para SCADA
│   ├── services/
│   │   ├── ingest_service.py  # Lógica de procesamiento de datos
│   │   └── scada_read_service.py # Lógica de lectura de datos
│   ├── security/
│   │   └── api_key.py         # Autenticación por API Key
│   ├── realtime/
│   │   ├── state_store.py     # Store de estado en tiempo real
│   │   └── ws_manager.py      # Gestor de conexiones WebSocket
│   ├── persist/
│   │   ├── queue.py           # Cola de persistencia
│   │   └── worker.py          # Worker para procesar cola
│   ├── state/
│   │   └── store.py           # Store de estado global
│   ├── deps/
│   │   └── realtime.py        # Dependencias de tiempo real
│   └── ws/
│       ├── manager.py         # Manager de WebSocket
│       └── routes.py          # Rutas WebSocket
├── repositories/
│   ├── scada_event_repository.py   # Repositorio de eventos SCADA
│   └── scada_read_repository.py    # Repositorio de lectura SCADA
├── requirements.txt            # Dependencias Python
├── README.md                   # Documentación del proyecto
└── ARCHITECTURE.md             # Este archivo
```

---

## 🔌 Componentes Principales

### 1. **FastAPI Application** (`app/main.py`)

Punto de entrada de la aplicación que:
- Configura routers para ingesta, lectura y WebSocket
- Define singletons: `state_store`, `ws_manager`, `persist_worker`
- Implementa ciclo de vida (lifespan) para inicializar/cerrar recursos
- Crea automáticamente las tablas en la base de datos

**Singletons inicializados:**
- `state_store`: Almacena estado en tiempo real en memoria
- `ws_manager`: Gestiona conexiones WebSocket activas
- `persist_worker`: Worker que procesa la cola de persistencia

### 2. **Configuración y Logging** (`app/core/`)

#### **config.py**
Gestiona settings de la aplicación usando Pydantic Settings:
- `DATABASE_URL`: URL de conexión a PostgreSQL
- `ENVIRONMENT`: Tipo de entorno (development, production)
- `LOG_LEVEL`: Nivel de logging

#### **logging.py**
Setup centralizado de logging:
- Configuración de formatters
- Niveles de logging configurables

### 3. **Modelos de Base de Datos** (`app/models/`)

#### **base.py**
Clase base DeclarativeBase para SQLAlchemy

#### **lagoon.py**
Modelo de Laguna:
- `id`: nombre_laguna (PK)
- `name`: Nombre de la laguna
- `location`: Ubicación
- `created_at`: Fecha de creación

#### **scada_minute.py**
Datos SCADA agregados por minuto:
- `id`: UUID (PK)
- `lagoon_id`: nombre_laguna (FK a lagoons)
- `timestamp`: Minuto completo (redondeado)
- `value_num`: Valor numérico (temperatura, pH, etc.)
- `value_bool`: Valor booleano
- **Restricción única**: `(lagoon_id, tag_id, bucket_ts)`

#### **scada_event.py**
Eventos booleanos con timestamps:
- `id`: UUID (PK)
- `lagoon_id`: nombre_laguna (FK a lagoons)
- `tag_id`: Identificador del sensor
- `event_type`: Tipo de evento
- `start_ts`: Timestamp de inicio
- `end_ts`: Timestamp de fin (NULL mientras esté abierto)
- `description`: Descripción del evento

### 4. **Routers (API Endpoints)** (`app/routers/`)

#### **health.py**
- `GET /health/` - Health check de la aplicación

#### **ingest.py**
- `POST /ingest/` - Ingesta de datos SCADA
- `GET /ingest/` - Obtener últimos datos ingertados
- Llama a `IngestService` para procesar datos
- Integra `state_store` y `ws_manager`

#### **scada_read.py**
- `GET /scada/read/` - Leer datos SCADA agregados
- Utiliza repositorio de lectura

#### **scada_ws.py**
- `WS /ws/scada` - WebSocket para datos en tiempo real
- Integra `ws_manager`

### 5. **Schemas Pydantic** (`app/schemas/`)

Validación de payloads y respuestas

### 6. **Servicios** (`app/services/`)

#### **ingest_service.py**
Lógica principal de procesamiento:
- Recibe datos SCADA del payload
- Valida y procesa
- Agrega datos por minuto
- Detecta eventos booleanos
- Envia a cola de persistencia (`persist_queue`)
- Notifica a clientes WebSocket vía `ws_manager`

#### **scada_read_service.py**
- Consulta datos desde repositorios
- Formatea respuestas
- Filtros y paginación

### 7. **Seguridad** (`app/security/`)

#### **api_key.py**
- Validación de API Key en headers
- Inyección de dependencia FastAPI
- Método: Header `X-API-Key`

### 8. **Persistencia en Tiempo Real** (`app/realtime/`)

#### **state_store.py** (`RealtimeStateStore`)
Almacena estado en memoria:
- Datos SCADA más recientes
- Estado de eventos activos
- Última actualización por tag

#### **ws_manager.py** (`WebSocketManager`)
Gestiona conexiones WebSocket:
- Mantiene lista de conexiones activas
- Broadcast de datos en tiempo real
- Manejo de desconexiones

### 9. **Cola de Persistencia** (`app/persist/`)

#### **queue.py** (`PersistenceQueue`)
Cola asincrónica para datos a persistir:
- Garantiza entrega confiable a BD
- Implementa reintentos
- Uso de asyncio.Queue

#### **worker.py** (`PersistWorker`)
Worker que consume la cola:
- Escribe datos a PostgreSQL
- Manejo de errores y reintentos
- Corre en background durante el lifespan de la app

### 10. **Repositorios** (`repositories/`)

Patrón Repository para acceso a datos:

#### **scada_event_repository.py**
- Consultas de eventos SCADA
- Create, read, update, delete
- Filtros por lagoon, tag, fecha

#### **scada_read_repository.py**
- Consultas de datos SCADA agregados
- Filtros avanzados
- Paginación

### 11. **Sesión de Base de Datos** (`app/db/`)

#### **session.py**
- Configuración de SQLAlchemy engine
- Session factory
- Dependency injection de sesiones
- Función `get_db()` para FastAPI

### 12. **Estado Global** (`app/state/`)

#### **store.py** (`RealtimeStateStore`)
Store centralizado de estado en tiempo real:
- Acceso desde servicios y routers
- Consistencia de datos
- Caché en memoria

### 13. **Dependencias** (`app/deps/`)

#### **realtime.py**
Dependencias compartidas:
- Inyección de `state_store`
- Inyección de `ws_manager`
- Inyección de `persist_worker`

---

## 🔄 Flujo de Datos

### Ingesta de Datos SCADA

```
POST /ingest/
    ↓
[Validación Pydantic]
    ↓
IngestService.process_data()
    ├─→ Guardar en state_store (en memoria)
    ├─→ Agregar datos por minuto
    ├─→ Detectar eventos booleanos
    ├─→ Enviar a persist_queue
    └─→ Broadcast vía WebSocket (ws_manager)
    ↓
Response JSON (202 Accepted)
    ↓
PersistWorker (background)
    ├─→ Lee de persist_queue
    ├─→ Guarda ScadaMinute a PostgreSQL
    ├─→ Guarda ScadaEvent a PostgreSQL
    └─→ Reintentos si hay error
```

### Lectura de Datos

```
GET /scada/read/?lagoon_id=xxx
    ↓
ScadaReadService.get_data()
    ↓
ScadaReadRepository.query()
    ↓
[PostgreSQL - SELECT]
    ↓
Response JSON (datos SCADA agregados)
```

### WebSocket en Tiempo Real

```
WS /ws/
    ↓
[Validación API Key]
    ↓
[Conexión WebSocket establecida]
    ↓
ws_manager registra conexión
    ↓
state_store envía estado inicial al cliente
    ↓
IngestService notifica cambios
    ↓
ws_manager broadcast a todos los clientes conectados
```

---

## 🔒 Seguridad

- **API Key Authentication**: Validación en header `X-API-Key`
- **CORS**: Configuración en FastAPI (ajustar según entorno)
- **SQL Injection**: Protegido por SQLAlchemy ORM con parámetros vinculados
- **Rate Limiting**: (Futuro)
- **HTTPS**: Recomendado en producción

---

## 📊 Patrones Utilizados

| Patrón | Uso |
|--------|-----|
| **Singleton** | `state_store`, `ws_manager`, `persist_worker` |
| **Dependency Injection** | FastAPI dependencies |
| **Repository Pattern** | Acceso a datos abstracto |
| **Service Layer** | Lógica de negocio separada de routers |
| **Factory Pattern** | Session factory para BD |
| **Observer Pattern** | Notificaciones WebSocket |
| **Async/Await** | Operaciones no bloqueantes |

---

## 🚀 Escalabilidad

### Capacidades Actuales
- Estado en memoria (`RealtimeStateStore`)
- Single worker para persistencia
- Datos agregados por minuto
- Timestamps con zona horaria

### Mejoras Futuras
- **Redis**: Para estado distribuido y caché
- **Message Broker**: Para cola distribuida de persistencia
- **Multiple Workers**: Para procesamiento distribuido
- **Sharding**: Partición de datos por laguna
- **Caching**: Redis para datos frecuentes
- **Compresión**: Compresión de datos históricos

---

## 📈 Monitoreo

- **Logging**: Centralizado en `app/core/logging.py`
- **Health Check**: Endpoint `GET /health/`
- **Métricas**: (Futuro - Prometheus)
- **Alertas**: (Futuro)

---

## 🗄️ Base de Datos

### Motor
PostgreSQL 12+

### Tablas Principales

| Tabla | Propósito |
|-------|-----------|
| `lagoons` | Información de lagunas |
| `scada_minutes` | Datos SCADA agregados por minuto |
| `scada_events` | Eventos booleanos con timestamps |

### Relaciones
- **ScadaMinute** → **Lagoon** (via `lagoon_id`)
- **ScadaEvent** → **Lagoon** (via `lagoon_id`)

```

---

## 📦 Dependencias Principales

```
fastapi==0.115.6              # Framework web moderno
uvicorn[standard]==0.32.1     # Servidor ASGI
SQLAlchemy==2.0.36            # ORM de base de datos
psycopg2-binary==2.9.10       # Driver PostgreSQL
pydantic==2.10.3              # Validación de datos
pydantic-settings==2.6.1      # Manejo de configuración
python-dotenv==1.0.1          # Carga de variables de entorno
```

---

## ⚙️ Configuración

### Variables de Entorno (`.env`)

```env
DATABASE_URL=postgresql://user:password@localhost:5432/crystal_lagoons
ENVIRONMENT=development
LOG_LEVEL=INFO
```

### Settings
- Cargados desde `config.py` en startup
- Válidos para toda la aplicación
- Inyectados donde sea necesario

---


Utilizar pytest con fixtures para:
- BD de prueba
- Cliente de prueba FastAPI
- Mocks de WebSocket

---

## 📝 Deployment

### Desarrollo
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Producción
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Con Gunicorn
```bash
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app
```

### Con Docker
```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

