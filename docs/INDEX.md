# 📚 Documentación Completa - Crystal Lagoons Backend

**Bienvenido a la documentación oficial del backend de Crystal Lagoons**

Esta documentación está organizada en 5 documentos principales para diferentes niveles de detalle y casos de uso.

---

##  Mapa de Documentación

```
┌────────────────────────────────────────────────────────────────────┐
│           ELIGE TU PUNTO DE ENTRADA SEGÚN TU ROL                  │
└────────────────────────────────────────────────────────────────────┘

🟩 [QUICK REFERENCE] 
   ├─ Comandos útiles
   ├─ Payloads comunes
   ├─ Troubleshooting rápido
   └─ Links a documentación
   └─→ Para: Desarrollador en prisa / Referencia rápida

🟦 [ARQUITECTURA Y FLUJO] 
   ├─ Visión general del sistema
   ├─ Descripción de componentes
   ├─ Flujo de inserción paso a paso
   ├─ Endpoints HTTP explicados
   ├─ Sistema WebSocket completo
   ├─ Modelos de base de datos
   ├─ Diagramas de arquitectura
   └─ FAQ com preguntas comunes
   └─→ Para: Nuevo desarrollador / Product Manager / Arquitecto

🟨 [GUÍA TÉCNICA DE DESARROLLO] 
   ├─ Setup y ejecución
   ├─ Estructura del código detallada
   ├─ 5 ejemplos prácticos completos
   │  ├─ Entender flujo ingest
   │  ├─ Cliente HTTP (cURL)
   │  ├─ Cliente WebSocket (JS/Python)
   │  ├─ Interactuar con estado
   │  └─ Query historial desde BD
   ├─ Testing (unit e integration)
   ├─ Debugging avanzado
   ├─ Extensiones comunes
   └─ Troubleshooting detallado
   └─→ Para: Desarrollador que quiere codificar

🟪 [DIAGRAMAS Y FLUJOS] 📊                (15-20 min)
   ├─ Arquitectura general (ASCII art)
   ├─ Flujo completo inserción (paso a paso)
   ├─ Ciclo de vida evento booleano
   ├─ Estado en memoria vs persistencia
   ├─ WebSocket snapshot vs tick
   ├─ Sincronización thread-safe
   ├─ Diagrama almacenamiento datos
   ├─ Matriz tipos de datos
   ├─ Escalabilidad y límites
   └─ Ciclo de vida aplicación
   └─→ Para: Visual learner / Entender arquitectura a fondo

🟥 [INDEX - ESTE ARCHIVO] 🗑️              (5 min)
   └─ Guía de navegación y vincularlos documentos

```

---

## ✨ Por Dónde Empezar

### Si eres NUEVO en el proyecto:

```
1️⃣  Leer: QUICK_REFERENCE.md (5 min)
    → Entender qué hace el sistema

2️⃣  Leer: ARQUITECTURA_Y_FLUJO.md (25 min)
    → Aprender componentes y flujo

3️⃣  Ver: DIAGRAMAS_FLUJOS.md (15 min)
    → Visualizar la arquitectura

4️⃣  Leer: GUIA_TECNICA_DESARROLLO.md (30 min)
    → Estar listo para codificar

⏱️  TOTAL: ~75 minutos para dominar el sistema
```

### Si necesitas IMPLEMENTAR una característica:

```
1️⃣  Consultar: QUICK_REFERENCE.md
    → Refrescar comandos y payloads

2️⃣  Ir a: GUÍA_TÉCNICA_DESARROLLO.md
    → Sección "Extensiones Comunes"
    → Encontrar caso similar

3️⃣  Consultar: ARQUITECTURA_Y_FLUJO.md
    → Sección "Dónde editar para..."
    → Entender qué archivo cambiar

4️⃣  Referencia: DIAGRAMAS_FLUJOS.md
    → Si necesitas depurar mientras codificas
```

### Si necesitas DEBUGGEAR un problema:

```
1️⃣  Ver: QUICK_REFERENCE.md
    → Sección "Troubleshooting Rápido"

2️⃣  Ir a: GUÍA_TÉCNICA_DESARROLLO.md
    → Sección "Debugging"
    → Encontrar error específico

3️⃣  Ir a: ARQUITECTURA_Y_FLUJO.md
    → Sección "Consideraciones Importantes"
    → Entender límites del sistema

4️⃣  Consulta: DIAGRAMAS_FLUJOS.md
    → Rastrear el flujo exacto de datos
```

### Si necesitas EXPLICAR a alguien más:

```
1️⃣  Compartir: QUICK_REFERENCE.md
    → Para que conozcan comandos

2️⃣  Compartir: DIAGRAMAS_FLUJOS.md
    → Para visualizar flujos

3️⃣  Compartir: ARQUITECTURA_Y_FLUJO.md
    → Para entender en detalle

4️⃣  Compartir: GUÍA_TÉCNICA_DESARROLLO.md
    → Si quieren hacer cambios
```

---

## 📖 Contenido de Cada Documento

### 1. QUICK_REFERENCE.md ⚡
**Archivo:** [QUICK_REFERENCE.md](./QUICK_REFERENCE.md)

Resumen ejecutivo de 1-2 páginas. Ideal para:
- Refrescar cómo se usan los endpoints
- Comandos comunes (curl, psql, etc)
- Payloads estándar
- Troubleshooting rápido
- Checklist de deploy

**Secciones:**
```
├─ Inicio Rápido
├─ 3 Formas de Interactuar (HTTP, WS, Query)
├─ Almacenamiento (ScadaEvent, ScadaMinute)
├─ Flujo Simplificado
├─ Dónde editar para cada necesidad
├─ Debugging Rápido
├─ Performance Tips
└─ Comandos Útiles
```

---

### 2. ARQUITECTURA_Y_FLUJO.md 📐
**Archivo:** [ARQUITECTURA_Y_FLUJO.md](./ARQUITECTURA_Y_FLUJO.md)

Documentación completa de la arquitectura (30-40 min de lectura).

**Secciones:**
```
├─ Visión General (stack tecnológico)
├─ Componentes Principales (6 componentes detallados)
│  ├─ FastAPI Application
│  ├─ Ingest Router
│  ├─ Ingest Service (core)
│  ├─ WebSocket Manager
│  ├─ Realtime State Store
│  └─ Persist Worker
├─ Flujo de Inserción de Datos (diagrama + ejemplo paso a paso)
├─ Endpoints HTTP (3 endpoints explicados)
├─ Sistema WebSocket (4 etapas de conexión)
├─ Modelos de Base de Datos (ScadaEvent, ScadaMinute)
├─ Estado y Sincronización (en memoria vs BD)
├─ Diagramas de Arquitectura (3 diagramas)
├─ Flujo de Desarrollador (cómo agregar funcionalidad)
├─ Consideraciones Importantes (thread-safety, pérdida datos, rendimiento)
└─ FAQ (5 preguntas frecuentes)
```

---

### 3. GUÍA_TÉCNICA_DESARROLLO.md 💻
**Archivo:** [GUIA_TECNICA_DESARROLLO.md](./GUIA_TECNICA_DESARROLLO.md)

Guía práctica con código (45-60 min).

**Secciones:**
```
├─ Setup y Ejecución (3 formas de ejecutar)
├─ Estructura del Código (árbol de carpetas)
├─ Ejemplos Prácticos (5 ejemplos con código completo)
│  ├─ Ejemplo 1: Entender flujo completo (código comentado)
│  ├─ Ejemplo 2: Cliente HTTP (cURL)
│  ├─ Ejemplo 3: Cliente WebSocket (JS + Python)
│  ├─ Ejemplo 4: Estado (AVANZADO)
│  └─ Ejemplo 5: Query Historial
├─ Testing (unit tests + integration tests)
├─ Debugging (logs, SQL queries, breakpoints, BD CLI)
├─ Extensiones Comunes (agregar endpoint, modelo, validación)
└─ Troubleshooting (5 problemas y soluciones)
```

**Código real:**
- Fragmentos de código funcional
- Tests ejecutables
- Comandos para ejecutar
- Ejemplos de payloads

---

### 4. DIAGRAMAS_FLUJOS.md 📊
**Archivo:** [DIAGRAMAS_FLUJOS.md](./DIAGRAMAS_FLUJOS.md)

Diagramas ASCII detallados (15-20 min).

**Secciones:**
```
├─ Arquitectura General del Sistema (diagrama grande)
├─ Flujo Completo Inserción (6 momentos, paso a paso)
├─ Ciclo de Vida Evento Booleano (3 eventos)
├─ Estado en Memoria vs Persistencia (diagrama 3 niveles)
├─ WebSocket: Snapshot vs Tick (secuencia)
├─ Sincronización Thread-Safe (locks)
├─ Diagrama Almacenamiento Datos (buffer → BD)
├─ Matriz de Tipos de Dato (tabla)
├─ Escalabilidad y Límites (recomendaciones)
└─ Ciclo de Vida Aplicación (startup → shutdown)
```

---

## 🎯 Matriz de Búsqueda

¿Necesitas respuesta a...?

| Pregunta | Documento | Sección |
|----------|-----------|---------|
| ¿Cómo inicio el servidor? | QUICK_REF | Inicio Rápido |
| ¿Cuál es el endpoint para enviar datos? | ARQUITECTURA | Endpoints HTTP |
| ¿Cómo funciona el WebSocket? | ARQUITECTURA | Sistema WebSocket |
| ¿Qué modelos de BD existen? | ARQUITECTURA | Modelos de BD |
| ¿Cómo funciona el flujo completo? | DIAGRAMAS | Flujo Completo |
| ¿Cómo escribo un test? | GUÍA_TÉCNICA | Testing |
| ¿Cómo debuggeo un problema? | GUÍA_TÉCNICA | Debugging |
| ¿Cómo agrego un nuevo endpoint? | GUÍA_TÉCNICA | Extensiones |
| ¿Cuál es la estructura del código? | GUÍA_TÉCNICA | Estructura Código |
| ¿Qué es thread-safe? | DIAGRAMAS | Sincronización |
| ¿Cómo conecto desde JavaScript? | GUÍA_TÉCNICA | Ejemplo 3 |
| ¿Cómo query histórico desde BD? | GUÍA_TÉCNICA | Ejemplo 5 |
| ¿Qué pasa si hay crash? | ARQUITECTURA | Consideraciones |
| ¿Puedo escalar a 1000 lagunas? | DIAGRAMAS | Escalabilidad |
| Mi WebSocket no conecta | QUICK_REF | Troubleshooting |
| | | |

---

## 🔗 Referencia Cruzada Rápida

### Archivos de Código Importantes

En los documentos se referencian estos archivos:

```
app/
├── main.py                        → Ver ARQUITECTURA (FastAPI App)
├── routers/ingest.py              → Ver ARQUITECTURA (Ingest Router)
├── services/ingest_service.py     → Ver ARQUITECTURA + GUÍA_TÉCNICA
├── ws/manager.py                  → Ver ARQUITECTURA (WebSocket Manager)
├── state/store.py                 → Ver ARQUITECTURA (State Store)
├── models/scada_event.py          → Ver ARQUITECTURA (Modelos BD)
├── models/scada_minute.py         → Ver ARQUITECTURA (Modelos BD)
└── ... (ver GUÍA_TÉCNICA para estructura completa)
```

---

## 🚀 Flujos Típicos de Trabajo

### Flujo: Agregar soporte para NUEVO tipo de sensor

```
1. Leer: QUICK_REFERENCE → Payloads
2. Leer: GUÍA_TÉCNICA → "Agregar nuevo tag"
3. Conc: No se necesita código (tags es dict genérico)
4. Test: Enviar payload con nuevo tag vía POST /ingest/scada
5. Ver: Datos llegan automáticamente a BD y WS
```

### Flujo: Investigar por qué datos no se guardan

```
1. Ver: QUICK_REFERENCE → Debugging Rápido
2. Leer: GUÍA_TÉCNICA → Debugging (logs, BD)
3. Rastrear: DIAGRAMAS → Flujo Completo
4. Verificar: db.commit() en el código
5. Test: SELECT en BD para verif persistencia
```

### Flujo: Explicar arquitectura a stakeholder

```
1. Mostrar: QUICK_REFERENCE → 3 Formas de Interactuar
2. Mostrar: DIAGRAMAS → Arquitectura General
3. Mostrar: DIAGRAMAS → Flujo Completo Inserción
4. Mostrar: QUICK_REFERENCE → Performance Tips (si pregunta escala)
```

---

## 📊 Estadísticas de Documentación

```
┌─────────────────────────────────────────────────────────────┐
│                  VOLUMEN DE DOCUMENTACIÓN                  │
├─────────────────────────┬──────────────┬─────────────────────┤
│ Documento               │ Líneas       │ Tiempo Lectura      │
├─────────────────────────┼──────────────┼─────────────────────┤
│ QUICK_REFERENCE         │ ~200         │ 5-10 min            │
│ ARQUITECTURA_Y_FLUJO    │ ~500         │ 20-30 min           │
│ GUIA_TECNICA            │ ~600         │ 45-60 min           │
│ DIAGRAMAS_FLUJOS        │ ~400         │ 15-20 min           │
│ INDEX (este archivo)    │ ~350         │ 10-15 min           │
├─────────────────────────┼──────────────┼─────────────────────┤
│ TOTAL                   │ ~2050 líneas │ 95-135 min (1.5-2h) │
└─────────────────────────┴──────────────┴─────────────────────┘

Nota: Con lecturas posteriores (búsquedas de temas específicos),
      el tiempo se reduce significativamente (<5 min por tópico).
```

---

## ✅ Checklist: "Estoy listo para..."

### ✓ Entender la arquitectura
- [ ] Leído QUICK_REFERENCE.md
- [ ] Leído ARQUITECTURA_Y_FLUJO.md
- [ ] Revisado DIAGRAMAS_FLUJOS.md
- [ ] Entiendo cómo fluyen los datos

### ✓ Desarrollar features
- [ ] Entiendo estructura de código (GUÍA_TÉCNICA)
- [ ] He visto ejemplos prácticos (GUÍA_TÉCNICA)
- [ ] Sé cómo hacer testing (GUÍA_TÉCNICA)
- [ ] Sé cómo debuggear (GUÍA_TÉCNICA)

### ✓ Mantener la aplicación
- [ ] Sé cómo iniciar/detener (QUICK_REFERENCE)
- [ ] Sé cómo verificar health (QUICK_REFERENCE)
- [ ] Sé cómo debuggear issues (QUICK_REFERENCE + GUÍA_TÉCNICA)
- [ ] He hecho query a la BD (GUÍA_TÉCNICA + Ejemplo 5)

### ✓ Escalabilidad y production
- [ ] Entiendo límites del sistema (DIAGRAMAS)
- [ ] Sé qué monitorear (QUICK_REFERENCE)
- [ ] Tengo checklist deploy (QUICK_REFERENCE)
- [ ] Entiendo thread-safety (DIAGRAMAS)

---

## 🔄 Mantener la Documentación al Día

Si cambias la arquitectura:

1. Actualizar el archivo relevante
2. Actualizar referencias cruzadas en otros documentos
3. Actualizar diagrama en DIAGRAMAS_FLUJOS.md
4. Actualizar FAQ en ARQUITECTURA_Y_FLUJO.md si aplica
5. Commit con mensaje: `docs: [categoría] cambio realizado`

---

## 📞 Contribuciones a la Documentación

¿Encontraste un error o algo confuso?

1. Abre un issue describiendo el problema
2. Sugiere cómo mejorarlo
3. Sean bienvenidas las contribuciones (PR)
4. Objetivo: Documentación clara para TODOS

---

## 🎓 Próximos Pasos Recomendados

### Después de leer toda la doc:

1. **Ejecutar**
   ```bash
   cd crystal-backend
   python -m uvicorn app.main:app --reload
   ```

2. **Experimentar**
   ```bash
   curl -X POST http://localhost:8000/ingest/scada \
     -d '{"lagoon_id": "test", "tags": {"temp": 28.5}}'
   ```

3. **Conectar WebSocket**
   ```bash
   wscat -c "ws://localhost:8000/ws/scada?lagoon_id=test"
   ```

4. **Hacer cambios**
   - Seguir ejemplo de "Extensiones" en GUÍA_TÉCNICA
   - Tests mientras haces cambios
   - Commit descriptivo

5. **Pedir review**
   - Compartir cambios con equipo
   - Documentar si cambió arquitectura
   - Actualizar docs si es necesario

---

## 📚 Lecturas Recomendadas Externas

- [FastAPI Oficial](https://fastapi.tiangolo.com/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)
- [WebSocket RFC 6455](https://tools.ietf.org/html/rfc6455)
- [PostgreSQL Docs](https://www.postgresql.org/docs/)
- [Python asyncio](https://docs.python.org/3/library/asyncio.html)

---

**Última actualización:** Febrero 9, 2026  
**Versión:** 1.0 - Documentación Completa  
**Autores:** Equipo de Desarrollo Crystal Lagoons  

---

## 🎯 Resumen

```
┌──────────────────────────────────────────────────────────────┐
│  TODA LA INFORMACIÓN QUE NECESITAS ESTÁ EN ESTOS 4 DOCS      │
│                                                              │
│  📖 ARQUITECTURA_Y_FLUJO.md          → Qué y cómo funciona   │
│  📖 GUIA_TECNICA_DESARROLLO.md       → Cómo codificar       │
│  📖 DIAGRAMAS_FLUJOS.md              → Visualizar flujos    │
│  📖 QUICK_REFERENCE.md               → Referencia rápida    │
│                                                              │
│  ¡Feliz desarrollo! 🚀                                       │
└──────────────────────────────────────────────────────────────┘
```
