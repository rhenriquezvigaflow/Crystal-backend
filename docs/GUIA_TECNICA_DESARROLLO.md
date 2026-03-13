# Guia Tecnica de Desarrollo - Crystal Lagoons Backend

**Ultima actualizacion:** 2026-03-13
**Publico:** Desarrolladores Python/FastAPI

---

## Tabla de contenidos

1. Setup rapido
2. Variables de entorno
3. Ejecutar aplicacion
4. Flujos de prueba con cURL
5. Estructura de codigo
6. Testing
7. Troubleshooting

---

## 1) Setup rapido

Requisitos:

- Python 3.10+
- PostgreSQL 14+
- pip

Instalacion:

```bash
cd crystal-backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Crear `.env` (ejemplo minimo):

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/crystal
COLLECTOR_API_KEY=replace-me
JWT_SECRET_KEY=replace-me
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
```

Preparar RBAC base:

```bash
psql "$DATABASE_URL" -f scripts/sql/create_rbac_tables.sql
python scripts/seed_roles.py
```

Opcional (historial con vistas continuas):

```bash
psql "$DATABASE_URL" -f scripts/sql/create_scada_continuous_aggregates.sql
```

---

## 2) Variables de entorno

Requeridas:

- `DATABASE_URL`
- `COLLECTOR_API_KEY`
- `JWT_SECRET_KEY`

Importantes:

- `JWT_ALGORITHM` (default `HS256`)
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default `60`)
- `INGEST_TIMEOUT_SEC` (default `125`)
- `SCADA_WATCHDOG_ENABLED` y familia `SCADA_WATCHDOG_*`

Nota:

- `app/core/config.py` usa `extra="forbid"`; variables no declaradas pueden romper carga de settings.

---

## 3) Ejecutar aplicacion

```bash
python -m uvicorn app.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/health
```

Respuesta esperada:

```json
{"status": "ok"}
```

---

## 4) Flujos de prueba con cURL

### 4.1 Login

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"Secret123!"}'
```

Guardar token:

```bash
TOKEN="<access_token>"
```

### 4.2 Ingest protegido por API key

```bash
curl -X POST http://localhost:8000/ingest/scada \
  -H "Content-Type: application/json" \
  -H "x-api-key: $COLLECTOR_API_KEY" \
  -d '{
    "lagoon_id":"laguna_1",
    "timestamp":"2026-03-13T14:30:45Z",
    "tags":{"bomba_1":1,"temperatura":28.5}
  }'
```

### 4.3 Lecturas SCADA (bearer)

```bash
curl "http://localhost:8000/scada/laguna_1/current" \
  -H "Authorization: Bearer $TOKEN"

curl "http://localhost:8000/scada/laguna_1/last-minute" \
  -H "Authorization: Bearer $TOKEN"

curl "http://localhost:8000/scada/laguna_1/pump-events/last-3" \
  -H "Authorization: Bearer $TOKEN"

curl "http://localhost:8000/scada/history/hourly?lagoon_id=laguna_1&start_date=2026-03-01T00:00:00Z&end_date=2026-03-13T23:59:59Z" \
  -H "Authorization: Bearer $TOKEN"
```

### 4.4 RBAC por permisos de laguna

```bash
curl "http://localhost:8000/lagoons" \
  -H "Authorization: Bearer $TOKEN"

curl -X PUT "http://localhost:8000/lagoons/laguna_1" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"values":{"timezone":"America/Santiago"}}'

curl -X POST "http://localhost:8000/control/pump" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"lagoon_id":"laguna_1","action":"start","payload":{}}'
```

### 4.5 API Crystal y Small

```bash
curl "http://localhost:8000/api/crystal/lagoons" \
  -H "Authorization: Bearer $TOKEN"

curl "http://localhost:8000/api/small/lagoons" \
  -H "Authorization: Bearer $TOKEN"
```

### 4.6 WebSocket

Ejemplo con query token:

```text
ws://localhost:8000/ws/scada?lagoon_id=laguna_1&token=<jwt>
```

Al conectar debe llegar `snapshot`; luego `tick` en cada ingest.

---

## 5) Estructura de codigo

```text
app/
  main.py                        # bootstrap + routers + CORS
  core/config.py                 # settings
  db/session.py                  # SessionLocal + get_db
  auth/
    auth.py                      # POST /auth/login
    jwt.py                       # create/decode token
    services/
      auth_service.py            # authenticate_user + login response
      lagoon_service.py          # permisos por laguna
    routers/
      lagoons_router.py          # /lagoons, /control/pump
  security/
    rbac.py                      # require_roles / require_permission / ws permission
    api_key.py                   # verify_collector_key
  routers/
    ingest.py                    # POST /ingest/scada
    scada_read.py                # /scada/{lagoon}/current,last-minute
    scada_event.py               # /scada/{lagoon}/pump-events/last-3
    crystal/*                    # API producto crystal
    small/*                      # API producto small
  scada/history/
    repo.py                      # resolución + view/fallback
    router.py                    # GET /scada/history/{resolution}
  state/store.py                 # estado realtime + payload
  ws/routes.py                   # websocket endpoints
```

---

## 6) Testing

Ejecutar todo:

```bash
pytest tests/ -v
```

Suites relevantes:

- `tests/test_auth_core.py`
- `tests/test_rbac.py`
- `tests/test_rbac_permissions.py`

Smoke recomendado despues de cambios en auth/RBAC:

1. login exitoso y login invalido.
2. endpoint protegido con y sin bearer.
3. websocket con token valido e invalido.
4. ingest con y sin `x-api-key`.

---

## 7) Troubleshooting

### Error: Missing bearer token / Invalid or expired token

- Verifica `Authorization: Bearer <token>`.
- Verifica `JWT_SECRET_KEY` y expiracion.

### Error: Invalid collector key

- Verifica `x-api-key` contra `COLLECTOR_API_KEY`.

### Error 403 en endpoints con token valido

- Revisar roles en JWT (`roles`).
- Revisar permisos por laguna en `vw_user_lagoons`.

### Error en historial por columnas/vistas

- Verifica que exista `scada_minute` con columna `bucket`.
- Si usas vistas continuas, aplicar script `create_scada_continuous_aggregates.sql`.

### WebSocket cierra con codigo 1008

- Token faltante o invalido.
- Usuario sin `can_view` para esa laguna.

### Fallas de arranque por settings

- Revisar `.env` y claves requeridas en `app/core/config.py`.

---

Documentos complementarios:

- [INDEX.md](./INDEX.md)
- [ARQUITECTURA_Y_FLUJO.md](./ARQUITECTURA_Y_FLUJO.md)
- [FLUJO_INSERCION.md](./FLUJO_INSERCION.md)
