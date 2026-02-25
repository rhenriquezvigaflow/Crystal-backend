# 🌊 Crystal Lagoons - SCADA Backend

API backend para la gestión y procesamiento de datos SCADA (Supervisory Control and Data Acquisition) en tiempo real desde múltiples lagunas de tratamiento de agua.

**Ultima actualizacion:** Febrero 25, 2026 | **Version:** 1.1
## 🚀 Características Principales

- **Ingesta de datos SCADA**: Recibe telemetría desde sistemas SCADA (Rockwell, Siemens, etc.)
- **Almacenamiento eficiente**: Datos agregados por minuto en PostgreSQL
- **Rastreo de eventos**: Monitoreo de eventos booleanos con timestamps de inicio/fin
- **WebSocket en tiempo real**: Transmisión de datos y estado en vivo a clientes conectados
- **Lectura rápida de estado**: Endpoints `/scada/{lagoon_id}/current` y `/scada/{lagoon_id}/last-minute`
- **Eventos de bombas (ultimos 3)**: Endpoint `/scada/{lagoon_id}/pump-events/last-3`
- **Consultas historicas**: `/scada/history/{resolution}` (hourly/daily/weekly)
- **Agregados continuos**: Script SQL versionado para vistas `hourly/daily/weekly`
- **Carga de zonas horarias**: Durante el arranque la aplicación inicializa timezones desde la tabla `lagoons` para normalizar timestamps
- **Watchdog SCADA**: Servicio que vigila stall/caídas en el flujo de datos
- **Cola de persistencia**: Worker asincrónico para garantizar persistencia de datos
- **API REST robusta**: Endpoints documentados con Swagger/OpenAPI

## 📚 Documentación Completa

**[➡️ VER DOCUMENTACIÓN COMPLETA](docs/INDEX.md)**

### Documentos Disponibles

| Documento | Tiempo | Descripción |
|-----------|--------|-------------|
| **[INDEX.md](docs/INDEX.md)** | 5 min | 🗺️ Mapa maestro de toda la documentación |
| **[ONE_PAGE_SUMMARY.md](docs/ONE_PAGE_SUMMARY.md)** | 5 min | 🎯 Resumen ejecutivo en 1 página |
| **[ARQUITECTURA_Y_FLUJO.md](docs/ARQUITECTURA_Y_FLUJO.md)** | 20-30 min | 📐 Arquitectura completa y flujos |
| **[GUIA_TECNICA_DESARROLLO.md](docs/GUIA_TECNICA_DESARROLLO.md)** | 45-60 min | 💻 Guía práctica con código |
| **[DIAGRAMAS_FLUJOS.md](docs/DIAGRAMAS_FLUJOS.md)** | 15-20 min | 📊 Diagramas ASCII detallados |
| **[ONBOARDING.md](docs/ONBOARDING.md)** | 4-6 horas | 🎓 Guía para nuevos desarrolladores |

### Empieza por aquí según tu rol:

- ** Nuevo en el proyecto** → [ONBOARDING.md](docs/ONBOARDING.md) (guía paso a paso)
- ** Desarrollador** → [ARQUITECTURA_Y_FLUJO.md](docs/ARQUITECTURA_Y_FLUJO.md) + [GUIA_TECNICA_DESARROLLO.md](docs/GUIA_TECNICA_DESARROLLO.md)
- ** Setup rápido** → leer secciones "Empieza por aquí" en [ARQUITECTURA_Y_FLUJO.md](docs/ARQUITECTURA_Y_FLUJO.md)
- ** Arquitecto/PM** → [ONE_PAGE_SUMMARY.md](docs/ONE_PAGE_SUMMARY.md) + [DIAGRAMAS_FLUJOS.md](docs/DIAGRAMAS_FLUJOS.md)

## 📋 Requisitos Previos

- Python 3.10+
- PostgreSQL 12+
- pip

## 🔧 Instalación Rápida

**Para setup detallado paso a paso:** [ONBOARDING.md](docs/ONBOARDING.md) o [GUIA_TECNICA_DESARROLLO.md](docs/GUIA_TECNICA_DESARROLLO.md#-setup-y-ejecución)

### 1. Clonar y Configurar

```bash
# Clonar repositorio
git clone <repository-url>
cd crystal-backend

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

### 2. Configurar Base de Datos

```bash
# Crear archivo .env
cat > .env << EOF
DATABASE_URL=postgresql://user:password@localhost:5432/crystal_lagoons
DEBUG=True
EOF

# Verificar que PostgreSQL está corriendo
psql -c "SELECT 1"

# Crear BD (si no existe)
psql -c "CREATE DATABASE crystal_lagoons;"

# Crear continuous aggregates para histórico (hourly/daily/weekly)
psql "$DATABASE_URL" -f scripts/sql/create_scada_continuous_aggregates.sql
```

### 3. Ejecutar Servidor

```bash
# Opción 1: Con script oficial
start.bat  # Windows
# o ./start.sh  # Linux/Mac

# Opción 2: Con uvicorn directo
python -m uvicorn app.main:app --reload

# ✅ Verificar
curl http://localhost:8000/health
# Respuesta: {"status":"ok"}
```

La API estará en: http://localhost:8000
- 📖 Swagger Docs: http://localhost:8000/docs
- 📖 ReDoc: http://localhost:8000/redoc

## 📡 Endpoints Principales

Para documentación completa de endpoints, ver [ARQUITECTURA_Y_FLUJO.md - Endpoints HTTP](docs/ARQUITECTURA_Y_FLUJO.md#-endpoints-http)

### Health Check
```bash
GET /health
# Respuesta: {"status":"ok"}
```

### Ingesta de Datos SCADA
```bash
POST /ingest/scada
# Body:
{
  "lagoon_id": "laguna_1",
  "ts": "2026-02-09T14:30:45Z",  # Opcional (ISO 8601 UTC)
  "tags": {
    "bomba": true,
    "temperatura": 28.5
  }
}
# Respuesta: {"ok": true}
```

### Consultas de Lectura
```bash
GET /scada/{lagoon_id}/current       # estado en memoria más reciente
GET /scada/{lagoon_id}/last-minute   # agregación por minuto
```

### Historial SCADA
```bash
GET /scada/history/hourly?lagoon_id=laguna_1&start_date=2026-02-01&end_date=2026-02-07
# devuelve series por tag según resolución (hourly|daily|weekly)
```

### Eventos de bombas (ultimos 3)
```bash
GET /scada/{lagoon_id}/pump-events/last-3
```

### WebSocket - Real-time
```
WS /ws/scada?lagoon_id=laguna_1
# Ejemplo: ws://localhost:8000/ws/scada?lagoon_id=laguna_1
# Conexión bidireccional para recibir snapshot inicial y ticks en vivo
```

Para más detalles: [Sistema WebSocket](docs/ARQUITECTURA_Y_FLUJO.md#-sistema-websocket-real-time)

## 🏗️ Arquitectura

**Para documentación completa de arquitectura:** [ARQUITECTURA_Y_FLUJO.md](docs/ARQUITECTURA_Y_FLUJO.md)

### Componentes Principales

```
SCADA Device 
    ↓ POST /ingest/scada
FastAPI Application
    ├─ Timezone Loader (carga zonas horarias desde `lagoons`)
    ├─ RealtimeStateStore (Estado en memoria)
    ├─ Watchdog SCADA (detecta stalls y reinicios)
    ├─ IngestService (Lógica de datos: buffering, eventos, persistencia)
    ├─ WebSocketManager (Conexiones bidireccionales)
    └─ PersistWorker (cola de escritura en segundo plano)
    ↓
PostgreSQL Database
    ├─ scada_event (Eventos de bombas)
    └─ scada_minute (Histórico agregado)
    ↓
Frontend (React/Vue)
    ├─ HTTP REST (ingest / reads / history)
    └─ WebSocket real-time
```

### Flujo de Inserción de Datos

1. **POST /ingest/scada** - Cliente envía datos
2. **Actualizar RealtimeStateStore** - Cache en memoria
3. **IngestService** - Buffering, eventos, persistencia
4. **PostgreSQL** - Guardar en BD
5. **Broadcast WebSocket** - Notificar clientes
6. **HTTP 200** - Responder al cliente

[Ver diagrama completo →](docs/DIAGRAMAS_FLUJOS.md#-flujo-completo-de-inserción-paso-a-paso)

## � Estructura de Carpetas

**Para descripción detallada:** [GUIA_TECNICA_DESARROLLO.md - Estructura](docs/GUIA_TECNICA_DESARROLLO.md#-estructura-del-código)

```
crystal-backend/
├── app/
│   ├── main.py                 # 🔴 Punto de entrada, singletons
│   ├── core/                   # Configuración y logging
│   ├── db/                     # Conexión a PostgreSQL
│   ├── models/                 # 🔴 Modelos SQLAlchemy (scada_event, scada_minute)
│   ├── routers/                # 🔴 Endpoints HTTP (POST /ingest/scada)
│   ├── schemas/                # Validación Pydantic
│   ├── services/               # 🔴 IngestService (core logic)
│   ├── state/                  # 🔴 RealtimeStateStore (estado en memoria)
│   ├── ws/                     # 🔴 WebSocket manager y routes
│   ├── persist/                # Worker de persistencia
│   ├── repositories/           # Acceso a datos
│   └── __pycache__/
├── docs/                       # 📚 DOCUMENTACIÓN COMPLETA
│   ├── INDEX.md               # Mapa maestro
│   ├── (antes QUICK_REFERENCE.md)    # archivo retirado - usar ARQUITECTURA_Y_FLUJO
│   ├── ARQUITECTURA_Y_FLUJO.md # Documentación completa
│   ├── GUIA_TECNICA_DESARROLLO.md # Guía con código
│   ├── DIAGRAMAS_FLUJOS.md    # Diagramas ASCII
│   ├── ONE_PAGE_SUMMARY.md    # Resumen 1 página
│   └── ONBOARDING.md          # Guía nuevos desarrolladores
├── tests/                      # Tests unitarios e integración
├── requirements.txt            # Dependencias Python
├── start.bat / start.sh       # Scripts de inicio
└── README.md                   # Este archivo
```

**Archivos críticos** (marcados 🔴): Estos son los que cambiarás la mayoría del tiempo.

## � Autenticación

Actualmente el sistema utiliza CORS abierto para desarrollo de frontend local. Configurado en `app/main.py`:

```python
CORSMiddleware(
    allow_origins=[
        "http://192.168.1.22",
        "http://localhost:5173",  # Vite dev
        "http://localhost:3000",  # React dev
    ],
    allow_credentials=True,
)
```

⚠️ **Nota:** Antes de producción, implementar autenticación JWT o API Key.

## 🔌 Dependencias Principales

| Librería | Uso |
|----------|-----|
| **FastAPI** | Framework web moderno |
| **SQLAlchemy** | ORM para base de datos |
| **PostgreSQL** | Base de datos relacional |
| **Pydantic** | Validación de datos |
| **WebSockets** | Comunicación real-time |

Ver [requirements.txt](requirements.txt) para lista completa.

## 📝 Logging

Configurado en `app/core/logging.py`. Nivel configurable con variable de entorno `LOG_LEVEL`.

```python
from app.core.logging import get_logger

logger = get_logger("mi_modulo")
logger.info("Información")
logger.error("Error")
```

**Más info:** [GUIA_TECNICA_DESARROLLO.md - Debugging](docs/GUIA_TECNICA_DESARROLLO.md#-debugging)

PostgreSQL es utilizado como base de datos principal. Las migraciones pueden realizarse usando SQLAlchemy ORM.

### Tablas Principales

| Tabla | Propósito |
|-------|-----------|
| **scada_event** | Eventos de ON/OFF de bombas con timestamps |
| **scada_minute** | Datos agregados por minuto (histórico) |
| **lagoons** | Información de lagunas |

**Detalles completos:** [Modelos de Base de Datos](docs/ARQUITECTURA_Y_FLUJO.md#-modelos-de-base-de-datos)

## 🧪 Testing

```bash
# Ejecutar todos los tests
pytest tests/ -v

# Ejecutar tests específicos
pytest tests/test_ingest.py -v

# Con coverage
pytest tests/ --cov=app --cov-report=html
```

**Ejemplos de tests:** [GUIA_TECNICA_DESARROLLO.md - Testing](docs/GUIA_TECNICA_DESARROLLO.md#-testing)

## 🚨 Troubleshooting

| Problema | Solución |
|----------|----------|
| `Connection refused` | Verificar PostgreSQL: `psql -c "SELECT 1"` |
| `404 /ingest/scada` | Verificar que la app está corriendo |
| `WebSocket connection failed` | Verificar CORS en main.py |
| `No se guardan datos` | Verificar `db.commit()` en el código |

**Troubleshooting completo:** revisar [ARQUITECTURA_Y_FLUJO.md](docs/ARQUITECTURA_Y_FLUJO.md#-endpoints-http) o [GUIA_TECNICA_DESARROLLO.md](docs/GUIA_TECNICA_DESARROLLO.md#-troubleshooting)

## 🚀 Performance & Escalabilidad

| Métrica | Recomendación |
|---------|---|
| Ingest rate | 1-100 msg/segundo ✅ |
| Lagunas simultáneas | 10-20 sin problemas ✅ |
| Clientes WebSocket | 50-100 por laguna ✅ |
| Límite buffer | 200,000 mensajes máx |

**Detalles:** [DIAGRAMAS_FLUJOS.md - Escalabilidad](docs/DIAGRAMAS_FLUJOS.md#-escalabilidad-y-límites)

## 🐛 Debugging

### Ver logs en tiempo real
```bash
# En la terminal donde corre la app, ves automáticamente:
# [BOOT] pump_last_on precargado: ...
# [UPDATE] lagoon=costa_del_lago
# [EVENT OPEN] tag_id=bomba_1
```

### Revisar estado en BD
```bash
psql -c "SELECT * FROM scada_event WHERE end_ts IS NULL;"
psql -c "SELECT * FROM scada_minute ORDER BY bucket DESC LIMIT 10;"
```

**Guía completa:** [GUIA_TECNICA_DESARROLLO.md - Debugging](docs/GUIA_TECNICA_DESARROLLO.md#-debugging)

## 🤝 Contribuir

Para contribuir al proyecto:

1. **Crear rama** desde `main` o `develop`
   ```bash
   git checkout -b feature/mi-feature-o-fix/mi-bug
   ```

2. **Hacer cambios** con tests
   ```bash
   pytest tests/ -v  # Asegurar que pasan
   ```

3. **Commit descriptivo**
   ```bash
   git commit -m "tipo: descripción
   
   Ejemplos:
   - feature: agregar nuevo endpoint
   - fix: corregir bug en sincronización
   - docs: actualizar documentación
   - refactor: simplificar ingest_service
   ```

4. **Push y Pull Request**
   ```bash
   git push origin feature/mi-feature
   ```
   Crear PR en GitHub con descripción clara

5. **Code Review** - Esperar aprobación, ajustar si es necesario

**Más detalles:** [ONBOARDING.md](docs/ONBOARDING.md#-parte-6-git--code-review-30-min)

## 📖 Documentación de Desarrollo

- **Nuevo en el proyecto:** [ONBOARDING.md](docs/ONBOARDING.md) (guía paso a paso - 4-6 horas)
- **Entender arquitecura:** [ARQUITECTURA_Y_FLUJO.md](docs/ARQUITECTURA_Y_FLUJO.md)
- **Hacer cambios:** [GUIA_TECNICA_DESARROLLO.md](docs/GUIA_TECNICA_DESARROLLO.md)
- **Referencia rápida:** usar la sección "Inicio rápido" de [ARQUITECTURA_Y_FLUJO.md](docs/ARQUITECTURA_Y_FLUJO.md)
- **Mapa navegación:** [INDEX.md](docs/INDEX.md)

## 📞 Soporte & Contacto

Para preguntas o issues:
1. Consultar documentación en `/docs`
2. Buscar en Issues existentes en GitHub
3. Contactar al equipo de desarrollo
4. Crear nuevo Issue si el problema persiste

## 📄 Licencia

[Especificar licencia de tu proyecto]

---

**Ultima actualizacion:** Febrero 25, 2026 | **Version:** 1.1
Para más información, ver [docs/INDEX.md](docs/INDEX.md)
