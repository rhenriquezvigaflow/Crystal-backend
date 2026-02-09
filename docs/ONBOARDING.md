# 🎓 Guía de Onboarding - Primeros Pasos

**"Acabo de unirme al proyecto, ¿por dónde empiezo?"**

Esta guía te acompañará en tus primeros días. Debería tomar **~4-6 horas** en total.

---

## 📅 Cronograma Sugerido

```
DÍA 1 (90 minutos)
├─ Parte 1: Entender el proyecto (30 min)
├─ Parte 2: Setup local (30 min)
├─ Parte 3: Explorar el código (30 min)
└─ Fin del día: Sistema funcionando localmente ✅

DÍA 2 (120 minutos)
├─ Parte 4: Primer cambio (30 min)
├─ Parte 5: Escribir un test (30 min)
├─ Parte 6: Git & Code Review (30 min)
└─ Fin del día: Primer PR enviado ✅

DÍA 3+ (según avance)
├─ Asignación de tareas basadas en skills
├─ Code review entre pares
└─ Escalada según sea necesario
```

---

## 📋 PARTE 1: Entender el Proyecto (30 min)

### Paso 1.1: Contexto Empresarial

```
❓ Pregunta a tu manager:
├─ ¿Qué es Crystal Lagoons?
├─ ¿Cuál es nuestro mercado?
├─ ¿Cuáles son los usuarios principales?
└─ ¿Qué problemas resolvemos?

Respuesta esperada: Tienes contexto de por qué existe el proyecto
```

### Paso 1.2: Documentación 101

**Leer estos documentos EN ORDEN:**

```
1️⃣  [5 min] Lee: ONE_PAGE_SUMMARY.md
    └─ Entender el sistema en 1 página

2️⃣  [10 min] Lee: QUICK_REFERENCE.md
    └─ Familiarizarte con comandos y payloads

3️⃣  [15 min] Lee: ARQUITECTURA_Y_FLUJO.md - Primeras 3 secciones
    ├─ Visión General
    ├─ Componentes Principales
    └─ Flujo de Inserción (primer párrafo)

⏱️ TIEMPO: 30 minutos
✅ META: Entiendes qué hace el sistema y cómo fluyen los datos
```

### Paso 1.3: Verificar Comprensión

```
Haz estas preguntas Y RESPÓNDELAS:

1. ¿Cuál es el endpoint principal para enviar datos?
   → POST /ingest/scada

2. ¿Cuáles son las 3 tablas principales en BD?
   → scada_event, scada_minute, (y lagoons si existe)

3. ¿Cuál es el propósito de WebSocket?
   → Enviar actualizaciones en tiempo real al frontend

4. ¿Qué hace el IngestService?
   → Procesa datos, crea eventos, persiste en BD

5. ¿Qué es RealtimeStateStore?
   → Cache en memoria del último estado de cada laguna

Si TODAS son correctas → Listo para siguiente parte ✅
Si hay dudas → Releer secciones relevantes ← NO avanzes
```

---

## 🛠️ PARTE 2: Setup Local (30 min)

### Paso 2.1: Clonar Repositorio

```bash
# Asegúrate estar en la carpeta correcta
cd ~/proyectos  # o tu carpeta de desarrollo

# Clonar repo (pide acceso si no lo tienes)
git clone https://github.com/tu-org/crystal-backend.git
cd crystal-backend

# Verificar que estás en rama correcta
git branch
# Deberías ver: (main) o (develop)
```

### Paso 2.2: Preparar Entorno

```bash
# 1. Crear entorno virtual
python -m venv venv

# 2. Activar entorno
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. Verificar que está activado
which python  # debería mostrar: .../venv/bin/python

# 4. Instalar dependencias
pip install -r requirements.txt

# 5. Verificar instalación
pip list  # debería ver: fastapi, sqlalchemy, etc
```

**Tiempo: ~10 minutos**

### Paso 2.3: Configurar BD

```bash
# 1. Verificar que PostgreSQL está corriendo
psql --version  # debería mostrar versión

# 2. Conectarse y crear BD
psql -U postgres
> CREATE DATABASE crystal;
> \q

# 3. Crear archivo .env
# En la raíz del proyecto (crystal-backend/):
echo "DATABASE_URL=postgresql://postgres:password@localhost:5432/crystal" > .env
echo "DEBUG=True" >> .env

# 4. Verificar conexión
psql postgresql://postgres:password@localhost:5432/crystal
> SELECT 1;
> \q
```

**Asegurate que:**
- ✅ PostgreSQL está instalado
- ✅ Usuario postgres existe
- ✅ BD "crystal" existe
- ✅ .env tiene DATABASE_URL correcta

**Tiempo: ~15 minutos**

### Paso 2.4: Ejecutar Primera Vez

```bash
# Desde crystal-backend/
python -m uvicorn app.main:app --reload

# Deberías ver:
# [00:00:00] Uvicorn running on http://0.0.0.0:8000
# [BOOT] pump_last_on precargado: ...
# [BOOT] PersistWorker iniciado
```

**En otra terminal:**
```bash
# Verificar que funciona
curl http://localhost:8000/health
# Respuesta: {"status":"ok"}
```

**✅ Si llegaste aquí: Sistema está corriendo localmente**

**Tiempo: ~5 minutos**

---

## 🔍 PARTE 3: Explorar el Código (30 min)

### Paso 3.1: Abrir en Editor

```bash
# Si usas VS Code
code .

# Si usas PyCharm
charm .

# O simplemente abre el proyecto manualmente
```

### Paso 3.2: Navegar la Estructura

```
✏️ TAREA: Explorar archivo por archivo
Tiempo: 15 minutos (no profundices, solo entiende qué hace cada uno)

Abre estos archivos EN ORDEN:

1️⃣  app/main.py
    Lectura rápida
    └─ Pregunta: ¿Qué singletons se crean?
    └─ Respuesta: RealtimeStateStore, WebSocketManager, PersistWorker

2️⃣  app/routers/ingest.py
    Lectura rápida
    └─ Pregunta: ¿Cuál es el endpoint y qué parámetros recibe?
    └─ Respuesta: POST /ingest/scada con lagoon_id, ts, tags

3️⃣  app/services/ingest_service.py (primeras 50 líneas)
    Lee solo hasta la función ingest()
    └─ Pregunta: ¿Qué hace el lock y por qué es importante?
    └─ Respuesta: Evita race conditions en multithreading

4️⃣  app/state/store.py
    Lectura rápida
    └─ Pregunta: ¿Qué almacena RealtimeStateStore?
    └─ Respuesta: tags, last_ts, pump_last_on, start_ts

5️⃣  app/ws/manager.py
    Lectura rápida
    └─ Pregunta: ¿Cómo envía mensajes a múltiples clientes?
    └─ Respuesta: broadcast() recorre lista de WebSockets

6️⃣  app/models/scada_event.py
    Lectura rápida
    └─ Pregunta: ¿Qué significa end_ts = NULL?
    └─ Respuesta: Evento abierto (bomba activa)

7️⃣  app/models/scada_minute.py
    Lectura rápida
    └─ Pregunta: ¿Qué es "bucket"?
    └─ Respuesta: Timestamp truncado al minuto para agregación
```

### Paso 3.3: Comprender el Flujo

```
✏️ TAREA: Trazar un request de inicio a fin
Tiempo: 15 minutos

EJERCICIO:
1. Abre DIAGRAMAS_FLUJOS.md
2. Lee la sección "Flujo Completo: Paso a Paso"
3. Abre app/routers/ingest.py
4. Abre app/services/ingest_service.py

PREGUNTA CLAVE:
Si envío este request:
    POST /ingest/scada
    {
      "lagoon_id": "laguna_1",
      "tags": {"bomba": true, "temp": 28.5}
    }

¿Qué EXACTAMENTE passa en cada archivo?

RESPUESTA:
1. ingest.py: Parsear payload, obtener referencias
2. Actualizar RealtimeStateStore (state.py)
3. Llamar ingest_service.ingest():
   a. Bufferizar valores
   b. Detectar cambio booleano (bomba: false→true)
   c. INSERT scada_event (abierto)
   d. Commit a BD
4. Broadcast WebSocket (manager.py)
5. Retornar 200 OK
```

---

## ✍️ PARTE 4: Primer Cambio (30 min)

### Paso 4.1: Crear una Rama Git

```bash
# Siempre crea rama antes de hacer cambios
git checkout -b feature/mi-primer-cambio

# Verificar que estás en rama correcta
git branch
# Deberías ver: * feature/mi-primer-cambio
#               main
```

### Paso 4.2: Cambio Pequeño

**Objetivo:** Agregar un simple log de debug

```python
# En app/routers/ingest.py, busca:

@router.post("/ingest/scada")
async def ingest_scada(payload: IngestPayload, request: Request):

# Agrega al inicio de la función:
print(f"[DEBUG] Ingest recibido: lagoon={payload.lagoon_id}")

# Luego:
await state.update(lagoon_id, tags, ts_iso)
print(f"[DEBUG] Estado actualizado para: {lagoon_id}")
```

### Paso 4.3: Probar el Cambio

```bash
# 1. Ejecutar la app (si ya está ejecutandose, reiniciar)
python -m uvicorn app.main:app --reload

# 2. En otra terminal, enviar request
curl -X POST http://localhost:8000/ingest/scada \
  -H "Content-Type: application/json" \
  -d '{"lagoon_id":"test","tags":{"temp":28.5}}'

# 3. En la terminal de la app, deberías ver:
# [DEBUG] Ingest recibido: lagoon=test
# [DEBUG] Estado actualizado para: test
```

### Paso 4.4: Commit y Push

```bash
# Ver qué cambió
git status
# Deberías ver: app/routers/ingest.py modificado

# Ver los cambios
git diff app/routers/ingest.py

# Agregar cambios
git add app/routers/ingest.py

# Commit con mensaje descriptivo
git commit -m "debug: agregar logs al endpoint ingest"

# Push (crear rama remota)
git push origin feature/mi-primer-cambio

# Ver el mensaje:
# remote: Create a pull request for 'feature/mi-primer-cambio' on GitHub
# → Hacer click al link para crear PR
```

### Paso 4.5: Code Review

```
✅ POST es automático en este proyecto
✅ Pedir review a un compañero lead

Esperar feedback y hacer ajustes si es necesario
```

---

## 🧪 PARTE 5: Escribir un Test (30 min)

### Paso 5.1: Entender Testing

```bash
# Ver tests existentes
ls tests/

# Los tests ya existentes te muestran el patrón
# Abre un archivo de test para ver la estructura
```

### Paso 5.2: Crear un Test Simple

```python
# Crea archivo: tests/test_mi_primer_test.py

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

class TestMiPrimerTest:
    def test_health_endpoint(self):
        """Verificar que el endpoint health funciona"""
        response = client.get("/health")
        
        # Verificaciones
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    
    def test_ingest_scada_minimal(self):
        """Verificar que ingest acepta payload mínimo"""
        response = client.post("/ingest/scada", json={
            "lagoon_id": "test",
            "tags": {"temperatura": 28.5}
        })
        
        assert response.status_code == 200
        assert response.json() == {"ok": True}
```

### Paso 5.3: Ejecutar Tests

```bash
# Ejecutar test específico
pytest tests/test_mi_primer_test.py -v

# Deberías ver:
# tests/test_mi_primer_test.py::TestMiPrimerTest::test_health_endpoint PASSED
# tests/test_mi_primer_test.py::TestMiPrimerTest::test_ingest_scada_minimal PASSED

# Ejecutar TODOS los tests
pytest tests/ -v
```

### Paso 5.4: Agregar Test a tu PR

```bash
git add tests/test_mi_primer_test.py
git commit -m "test: agregar tests básicos"
git push origin feature/mi-primer-cambio
```

---

## 📊 PARTE 6: Git & Code Review (30 min)

### Paso 6.1: Git Básico

**Operaciones que usarás diariamente:**

```bash
# Ver estado actual
git status

# Ver cambios sin stagear
git diff

# Stagear cambios
git add archivo.py
git add .  # Todos los cambios

# Ver cambios stageados
git diff --staged

# Commit
git commit -m "tipo: descripción corta"

# Push (primera vez crea rama remota)
git push origin nombre-rama

# Push (siguientes veces)
git push

# Actualizar rama local desde remoto
git pull

# Ver historial
git log --oneline -10  # Últimos 10 commits
```

**Mensajes de commit:**
```
formato: tipo: descripción

Ejemplos válidos:
- feature: agregar nuevo endpoint GET /stats
- fix: corregir bug en sincronización
- docs: actualizar README
- refactor: simplificar ingest_service
- test: agregar test de API
- debug: agregar logs temporales
```

### Paso 6.2: Flujo Pull Request

```
1. Hacer cambios en rama local
   └─ git checkout -b feature/nombre

2. Commit + push
   └─ git push origin feature/nombre

3. Ir a GitHub → Crear PR
   ├─ Título descriptivo
   ├─ Descripción de cambios
   ├─ Reference a issues si aplica (#123)
   └─ Revisar cambios en "Files changed"

4. Esperar reviews
   ├─ Responder comentarios
   ├─ Hacer commits adicionales si es necesario
   └─ Esperar aprobación ✅

5. Merge a main
   └─ Click "Merge pull request" en GitHub

6. Borrar rama
   └─ Click "Delete branch"

7. Actualizar local
   └─ git checkout main && git pull
```

### Paso 6.3: Checklist Antes de Hacer PR

```
ANTES DE PUSHEAR:

☐ Mi código funciona localmente
☐ Ejecuté todos los tests
  └─ pytest tests/ -v
☐ Mi código sigue el estilo del proyecto
  └─ No hay imports sin usar
  └─ Variables con nombres claros
☐ Agregué tests si es necesario
☐ Actualicé documentación si cambié arquitectura
☐ Commit message es claro
  └─ Ej: "feature: agregar validación de lagoon_id"
☐ Sé qué cambios hice (git diff)
☐ No incluyo credenciales ni .env
```

---

## 🎯 Fin del Onboarding

### ✅ Llegas aquí después de 4-6 horas

```
DÍA 1 (90 min) - HECHO
├─ ✓ Entiendes qué es Crystal Lagoons
├─ ✓ Sistema funcionando localmente
├─ ✓ Exploraste el código
└─ ✓ Hiciste tu primer cambio

DÍA 2 (120 min) - HECHO
├─ ✓ Escribiste tu primer test
├─ ✓ PR enviado y mergeado
├─ ✓ Aprendiste flujo Git

RESULTADO:
└─ ✅ Eres capaz de hacer cambios simples
```

### Próximos Pasos

```
◼️ Semana 1-2:
├─ Tareas simples (bug fixes, pequeños features)
├─ Code reviews en PRs de otros
├─ Profundizar en 1-2 módulos específicos
└─ Preguntar dudas SIN miedo

◼️ Semana 3-4:
├─ Tareas medianas (nuevos endpoints, cambios en BD)
├─ Diseño de soluciones con equipo
└─ Pairs with senior developers

◼️ Mes 2+:
├─ Tareas mayores (refactoring, features complejas)
├─ Mentoring a nuevos developers
└─ Ownership de módulos específicos
```

---

## 💬 FAQ Onboarding

### P: ¿Cuál es la documentación principal?

**R:** Los 6 documentos en `/docs`:
1. ONE_PAGE_SUMMARY.md - Resumen de 1 página
2. QUICK_REFERENCE.md - Referencia rápida
3. ARQUITECTURA_Y_FLUJO.md - Documentación completa
4. GUIA_TECNICA_DESARROLLO.md - Guía con código
5. DIAGRAMAS_FLUJOS.md - Diagramas ASCII
6. INDEX.md - Índice maestro

---

### P: ¿Cómo hago preguntas?

**R:** En orden de preferencia:
1. Busca en la documentación primero
2. Pregunta a tu pair programmer (si tienes)
3. Pregunta en canal #help de Slack
4. Abre discussion en GitHub

---

### P: Me bloqueé con un error, ¿qué hago?

**R:**
1. Lee el error completo (línea + stack trace)
2. Busca en documentación → sección troubleshooting
3. Pregunta a equipo
4. Crea un issue en GitHub si es bug

---

### P: ¿Cómo aprendo más sobre asyncio/SQLAlchemy?

**R:**
1. Docs oficiales (enlaces en ARQUITECTURA_Y_FLUJO.md)
2. Ejemplos en el código
3. Pide pair session con senior
4. Recursos externos (Real Python, etc)

---

### P: ¿Cuándo hago mi primer PR?

**R:** Después de completar **PARTE 4** (primer cambio)
- Debe ser cambio pequeño (bug fix o feature simple)
- Incluye tests si es lógica nueva
- Pide review a 1 persona senior

---

### P: ¿Qué si rompí algo?

**R:** **NO ENTRES EN PÁNICO**
1. Ejecuta `git status` para ver qué cambió
2. Si no hasceado: `git checkout archivo.py`
3. Si ya committes: `git revert <commit-hash>`
4. Si ya pushes: Avisa a equipo para ayudar

---

## 📞 Recursos Rápidos

| Necesidad | Ubicación |
|-----------|-----------|
| Setup inicial | PARTE 2 de esta guía |
| Cómo funciona el sistema | ONE_PAGE_SUMMARY.md |
| Comandos útiles | QUICK_REFERENCE.md |
| Entender arquitectura | ARQUITECTURA_Y_FLUJO.md |
| Código con ejemplos | GUIA_TECNICA_DESARROLLO.md |
| Flujos visuales | DIAGRAMAS_FLUJOS.md |
| Mapa de documentación | INDEX.md |

---

## 🎓 Recursos Externos Opcionales

```
Para profundizar (NO obligatorio en onboarding):

├─ FastAPI: https://fastapi.tiangolo.com/
├─ SQLAlchemy: https://docs.sqlalchemy.org/
├─ PostgreSQL: https://www.postgresql.org/docs/
├─ Python asyncio: https://docs.python.org/3/library/asyncio.html
└─ WebSockets: https://developer.mozilla.org/en-US/docs/Web/API/WebSocket
```

---

<div align="center">

## ¡Bienvenido al equipo! 🎉

**Acabas de completar el onboarding**

Estás listo para:
- ✅ Entender cómo funciona el sistema
- ✅ Hacer cambios simples
- ✅ Escribir tests
- ✅ Colaborar con Git

**Próximo:
Pedir tu primera tarea a tu manager**

</div>

---

**Última actualización:** Febrero 9, 2026  
**Tiempo total de onboarding:** 4-6 horas  
**Si tienes dudas:** Pregunta sin miedo, todos pasamos por esto 😊
