# Guia Tecnica de Desarrollo - Crystal Lagoons Backend

**Ultima actualizacion:** 2026-04-09
**Publico:** Desarrolladores Python/FastAPI

---

## 1) Setup rapido

Requisitos:

- Python 3.10+
- PostgreSQL 14+
- pip

Instalacion:

```bash
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
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
```

Variables utiles:

```env
INGEST_TIMEOUT_SEC=125
SCADA_LAYOUT_CACHE_TTL_SEC=300
LAYOUT_CONFIG_CACHE_TTL_SEC=300
```

---

## 2) Ejecutar aplicacion

```bash
python -m uvicorn app.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/health
```

Respuesta esperada:

```json
{"status":"ok"}
```

---

## 3) Estructura de codigo

```text
app/
  main.py                         # bootstrap, routers, lifespan
  routers/
    ingest.py                     # POST /ingest/scada
    scada_layouts.py              # /layouts + /lagoons/{id}/mapping
    crystal/lagoons.py            # endpoints producto Crystal
    small/lagoons.py              # endpoints producto Small
  layout_config/
    repository.py                 # DB layouts/mapping/collector_tags
    schemas.py                    # Pydantic contracts
    service.py                    # cache, validacion, update
  models/
    layout.py                     # tabla layouts
    lagoon_layout_mapping.py      # tabla lagoon_layout_mapping
    lagoon.py                     # tabla lagoons
  scada/
    layout_resolver.py            # normalizacion layout_id
    history/repo.py               # historico view/fallback
  services/
    ingest_service.py             # persistencia SCADA
  state/store.py                  # realtime state
  ws/routes.py                    # websocket
  alarms/                         # motor alarmas
```

---

## 4) Probar layout SCADA

Obtener layout:

```bash
curl "http://localhost:8000/layouts/layout1" \
  -H "Authorization: Bearer $TOKEN"
```

Obtener mapping de laguna:

```bash
curl "http://localhost:8000/lagoons/costa_del_lago/mapping" \
  -H "Authorization: Bearer $TOKEN"
```

Obtener configuracion producto:

```bash
curl "http://localhost:8000/api/crystal/lagoons/costa_del_lago/layout-config" \
  -H "Authorization: Bearer $TOKEN"
```

Actualizar mapping:

```bash
curl -X PUT "http://localhost:8000/api/crystal/lagoons/costa_del_lago/layout-config" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "layout_id": "layout1",
    "mapping_json": {
      "pressure_1": { "tag": "PT117_R_SCADA", "label": "PT_117" }
    }
  }'
```

Notas:

- El `PUT` requiere permiso de edicion para la laguna.
- Si una clave de `mapping_json` no existe en `layout.elements[].id`, devuelve `422`.
- El servicio actualiza `lagoons.scada_layout` con el `layout_id` enviado.

---

## 5) Historico

```bash
curl "http://localhost:8000/api/crystal/history?lagoon_id=costa_del_lago&start_date=2026-04-09T00:00:00Z&end_date=2026-04-09T23:59:59Z&resolution=hourly" \
  -H "Authorization: Bearer $TOKEN"
```

Respuesta esperada:

```json
{
  "lagoon_id": "costa_del_lago",
  "resolution": "hourly",
  "source": "table",
  "series": [
    {
      "tag": "PT117_R_SCADA",
      "points": [
        { "timestamp": "2026-04-09T12:00:00Z", "value": 2.34 }
      ]
    }
  ]
}
```

---

## 6) Testing

Ejecutar suite completa:

```bash
python -m pytest -q
```

Tests relevantes para layouts:

- `tests/test_scada_layouts.py`

Smoke recomendado:

1. `GET /health`.
2. login valido.
3. `GET /layouts/layout1`.
4. `GET /lagoons/{id}/mapping`.
5. `GET /api/{product}/lagoons/{id}/layout-config`.
6. `GET /api/{product}/history`.
7. WebSocket `/ws/scada/{id}`.

---

## 7) Troubleshooting rapido

### Backend no arranca por `Lagoon is not defined`

- Revisar import `from app.models.lagoon import Lagoon` en `app/main.py`.

### Mapping no muestra tarjetas

- Revisar `collector_tag_registry` para la laguna.
- Si el tag no esta habilitado por collector, el frontend lo oculta.
- Para elementos que siempre deben verse, usar `always_visible=true` en el layout.

### `PUT layout-config` devuelve 422

- Alguna clave del mapping no existe en `layout.json_definition.elements[].id`.

### Historico muestra series vacias

- Revisar rango de fechas.
- Revisar si hay datos en `scada_minute`.
- Recordar que frontend filtra tags de estado, WM y RETRO para graficos.

### Valores realtime `--`

- Puede no haber WebSocket o tag no presente en `tags`.
- El mapa se muestra igualmente despues de 7 segundos para lagunas desconectadas.
