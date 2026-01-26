# Crystal Lagoons SCADA Backend

API backend para la gestión y procesamiento de datos SCADA (Supervisory Control and Data Acquisition) en tiempo real desde múltiples lagunas de tratamiento de agua.

## 🚀 Características Principales

- **Ingesta de datos SCADA**: Recibe telemetría desde sistemas SCADA (Rockwell, Siemens, etc.)
- **Almacenamiento eficiente**: Datos agregados por minuto en PostgreSQL
- **Rastreo de eventos**: Monitoreo de eventos booleanos con timestamps de inicio/fin
- **WebSocket en tiempo real**: Transmisión de datos y estado en vivo a clientes conectados
- **Cola de persistencia**: Worker asincrónico para garantizar persistencia de datos
- **API REST robusta**: Endpoints documentados con Swagger/OpenAPI

## 📋 Requisitos Previos

- Python 3.10+
- PostgreSQL 12+
- pip

## 🔧 Instalación

1. **Clonar el repositorio**
```bash
git clone <repository-url>
cd crystal-backend
```

2. **Crear entorno virtual**
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

3. **Instalar dependencias**
```bash
pip install -r requirements.txt
```

4. **Configurar variables de entorno**
Crear archivo `.env` en la raíz del proyecto:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/crystal_lagoons
ENVIRONMENT=development
LOG_LEVEL=INFO
```

5. **Crear base de datos**
```bash
python -c "from app.db.session import engine; from app.models.base import Base; Base.metadata.create_all(bind=engine)"
```

## ▶️ Ejecución

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

La API estará disponible en `http://localhost:8000`
- Documentación Swagger: `http://localhost:8000/docs`
- Documentación ReDoc: `http://localhost:8000/redoc`

## 📡 Endpoints Principales

### Health Check
- `GET /health/` - Verificar estado de la aplicación

### Ingesta de Datos
- `POST /ingest/` - Enviar datos SCADA
- `GET /ingest/` - Obtener últimos datos ingertados

### Lectura SCADA
- `GET /scada/read/` - Leer datos SCADA almacenados

### WebSocket
- `WS /ws/` - Conexión WebSocket para datos en tiempo real

## 🏗️ Arquitectura

Para detalles sobre la arquitectura de la aplicación, ver [ARCHITECTURE.md](ARCHITECTURE.md)

## 📦 Estructura de Carpetas

```
app/
├── core/              # Configuración y logging
├── db/                # Configuración de base de datos
├── models/            # Modelos SQLAlchemy
├── routers/           # Endpoints de la API
├── schemas/           # Schemas Pydantic
├── services/          # Lógica de negocio
├── realtime/          # Estado en tiempo real y WebSocket
├── persist/           # Persistencia de datos
└── ws/                # Gestión de WebSocket
repositories/         # Acceso a datos
```

## 🔒 Autenticación

Actualmente la aplicación utiliza autenticación por API Key. Las claves deben incluirse en el header:
```
X-API-Key: <your-api-key>
```

## 🗄️ Base de Datos

PostgreSQL es utilizado como base de datos principal. Las migraciones pueden realizarse usando SQLAlchemy ORM.

### Tablas Principales
- `lagoons` - Información de lagunas
- `scada_minutes` - Datos SCADA agregados por minuto
- `scada_events` - Eventos booleanos con timestamps

## 🔌 Dependencias Principales

- **FastAPI**: Framework web moderno
- **SQLAlchemy**: ORM para base de datos
- **PostgreSQL**: Base de datos relacional
- **Pydantic**: Validación de datos
- **WebSockets**: Comunicación en tiempo real

Ver [requirements.txt](requirements.txt) para la lista completa.

## 📝 Logging

La aplicación utiliza el módulo `logging` de Python configurado en `app/core/logging.py`. Nivel de logging configurable mediante variable de entorno `LOG_LEVEL`.

## 🚨 Manejo de Errores

La API retorna códigos de estado HTTP estándar y mensajes de error detallados en formato JSON.

## 🤝 Contribuir

Para contribuir:
1. Crear un branch para la característica
2. Hacer commits descriptivos
3. Crear un Pull Request

## 📄 Licencia

[Especificar licencia]

## 📧 Contacto

Para preguntas o soporte, contactar al equipo de desarrollo.
