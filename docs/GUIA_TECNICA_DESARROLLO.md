# Guia Tecnica de Desarrollo - Crystal Lagoons Backend

**Ultima actualizacion:** 2026-06-12  
**Publico:** Desarrolladores Python/FastAPI

## 1. Setup Rapido

Requisitos:

- Python 3.10+
- PostgreSQL
- pip

Instalacion:

```powershell
cd crystal-backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

`.env` minimo:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/crystal
COLLECTOR_API_KEY=replace-me
JWT_SECRET_KEY=replace-me
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1080
```

Variables utiles:

```env
INGEST_REQUEST_TIMEOUT_SEC=125
SCADA_RUNTIME_PLC_OFFLINE_TIMEOUT_SEC=30
```

## 2. Ejecutar Aplicacion

```powershell
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8090
```

Health check:

```powershell
curl http://localhost:8090/health
```

Respuesta esperada:

```json
{"status":"ok"}
```

## 3. Estructura de Codigo

```text
app/
  main.py                         # bootstrap, routers, lifespan
  routers/
    health.py                     # /health
    ingest.py                     # POST /ingest/scada
    scada.py                      # /scada/{lagoon_id}/realtime|history|kpis
    events.py                     # /scada/{lagoon_id}/events|pump-events
    websocket.py                  # /ws/scada/{lagoon_id} legacy, /ws/{product}/{lagoon_id}
    alarm_thresholds.py           # /alarms/{lagoon_id}/thresholds/pt-fit
    email.py                      # /email/test-alert
    small/control.py              # /small/control
    small/chemicals.py            # /small/chemicals
  modules/
    shared/product_router.py      # /{product}/lagoons|history|current
    crystal/router.py             # /crystal/*
    small/router.py               # /small/*
  auth/
    auth.py                       # /auth/login
    routers/lagoons_router.py     # /lagoons, /control/pump
    services/lagoon_service.py    # permisos por producto/laguna
  models/
    lagoon.py                     # tabla lagoons
    role.py, user.py, user_role.py
    scada_minute.py, scada_event.py
  services/
    ingest_service.py
    scada_query_service.py
    scada_event_service.py
    email_service.py
  state/store.py                  # realtime state
  alarms/                         # motor alarmas
```

## 4. Probar Flujo Basico

Login:

```powershell
curl -X POST "http://localhost:8090/auth/login" `
  -H "Content-Type: application/json" `
  -d '{"email":"user@domain.com","password":"secret"}'
```

Lagunas:

```powershell
curl "http://localhost:8090/lagoons" -H "Authorization: Bearer $TOKEN"
```

Lagunas por producto:

```powershell
curl "http://localhost:8090/small/lagoons" -H "Authorization: Bearer $TOKEN"
curl "http://localhost:8090/crystal/lagoons" -H "Authorization: Bearer $TOKEN"
```

Historico:

```powershell
curl "http://localhost:8090/crystal/history?lagoon_id=costa_del_lago&start_date=2026-04-27T00:00:00Z&end_date=2026-04-27T23:59:59Z&resolution=hourly" `
  -H "Authorization: Bearer $TOKEN"
```

Realtime HTTP:

```powershell
curl "http://localhost:8090/scada/costa_del_lago/realtime" `
  -H "Authorization: Bearer $TOKEN"
```

WebSocket:

```text
ws://localhost:8090/ws/crystal/costa_del_lago?token=<jwt>
```

## 5. Ingest

```powershell
curl -X POST "http://localhost:8090/ingest/scada" `
  -H "X-Api-Key: $env:COLLECTOR_API_KEY" `
  -H "Content-Type: application/json" `
  -d '{"lagoon_id":"costa_del_lago","product_type":"crystal","tags":{"PT117_R_SCADA":2.31,"P006_STS_SCADA":1}}'
```

Resultado esperado:

- `scada_minute` actualizado;
- `scada_event` si hubo cambios de estado;
- alarmas evaluadas;
- tick WebSocket emitido.

Small simulator:

```powershell
python scripts\upsert_small_sim_lagoon.py
curl -X POST "http://localhost:8090/ingest/scada" `
  -H "X-Api-Key: $env:COLLECTOR_API_KEY" `
  -H "Content-Type: application/json" `
  -d '{"lagoon_id":"small_sim","product_type":"small","tags":{"PT-123":1.4,"AE-100":650,"AE-022":7.2,"TEMP":28.4,"ORP":650,"Dosif":1.25}}'
```

## 6. Testing

Ejecutar suite completa:

```powershell
python -m pytest -q
```

Tests relevantes:

- `tests/test_health_endpoints.py`
- `tests/test_ingest_minute_persistence.py`
- `tests/test_websocket_security.py`
- `tests/test_auth_service.py`
- `tests/test_alarm_thresholds_endpoints.py`
- `tests/test_email_service.py`

## 7. Troubleshooting Rapido

### Backend no arranca por seguridad

- Revisar `JWT_SECRET_KEY`.
- Revisar `COLLECTOR_API_KEY`.
- Evitar secretos por defecto en entornos no dev.

### Laguna no aparece

- Revisar `lagoons.enable`.
- Revisar `product_type`.
- Revisar `vw_user_lagoons` o rol por producto.

### Historico muestra series vacias

- Revisar rango de fechas.
- Revisar datos en `scada_minute`.
- Revisar si la vista agregada existe o si aplica fallback.

### Valores realtime `--` en frontend

- Revisar WebSocket.
- Revisar que el collector envie los tags usados por `src/assets/positions/{lagoon_id}.json`.
- Revisar `RealtimeStateStore` en `/health/ready`.
