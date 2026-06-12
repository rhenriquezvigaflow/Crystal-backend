# Small Lagoons Backend

**Actualizado:** 2026-06-12

Esta guia resume el soporte backend para el producto `small` y el simulador `small_sim`.

## Modelo de Producto

La tabla `lagoons` separa cada laguna por `product_type`:

- `crystal`
- `small`

El enum vive en `app.models.role.ProductType` y tambien se usa en `roles.product_type`.

Reglas principales:

- una laguna Small debe existir en `lagoons` con `product_type = 'small'`;
- los roles Small son `AdminSmall` y `VisualSmall`;
- `SuperAdmin` puede acceder a ambos productos;
- el collector puede enviar `product_type: "small"` en `/ingest/scada`;
- si el payload declara un producto distinto al de `lagoons`, ingest responde `409`.

## Alta Rapida de `small_sim`

El script:

```powershell
python scripts\upsert_small_sim_lagoon.py
```

crea o actualiza:

- `id`: `small_sim`
- `name`: `Small Simulator`
- `plc_type`: `simulator`
- `timezone`: `America/Santiago`
- `product_type`: `small`

Despues de ejecutarlo, reiniciar el backend para precargar timezone y metadata realtime.

## Endpoints Productizados

Directo contra FastAPI local:

- `GET /small/lagoons`
- `GET /small/dashboard`
- `GET /small/lagoons/{lagoon_id}/last-minute`
- `GET /small/lagoons/{lagoon_id}/current`
- `GET /small/history?lagoon_id=...`
- `GET /small/lagoons/{lagoon_id}/pump-events/last-3`
- `GET /small/lagoons/{lagoon_id}/pump-events/report.xlsx`
- `POST /small/tags/write`

Detras de proxy con `root_path="/api"`, el frontend los consume como `/api/small/...`.

## Control y Quimicos Small

Endpoints operativos:

- `POST /small/control`
- `PUT /small/control`
- `GET /small/chemicals`
- `POST /small/chemicals`
- `DELETE /small/chemicals`

Todos validan JWT, rol Small y acceso de la laguna esperada.

## WebSocket

Endpoint productizado:

```text
WS /ws/small/{lagoon_id}
```

El endpoint valida que la laguna exista y que `lagoons.product_type = 'small'`.

## Ingest desde Collector

Ejemplo:

```json
{
  "lagoon_id": "small_sim",
  "product_type": "small",
  "timestamp": "2026-06-12T12:00:00Z",
  "tags": {
    "PT-123": 1.4,
    "AE-100": 650,
    "AE-022": 7.2,
    "TEMP": 28.4,
    "ORP": 650,
    "Dosif": 1.25
  }
}
```

Validaciones:

- `lagoon_id` se normaliza con `normalize_lagoon_id`;
- la laguna debe estar habilitada (`enable = true`);
- `product_type` es opcional, pero si viene debe coincidir con la tabla `lagoons`;
- los tags se sincronizan con `sp_sync_collector_tags_and_alarms` si la funcion existe.

## Checklist de Diagnostico

1. `SELECT id, product_type, enable FROM lagoons WHERE id = 'small_sim';`
2. El usuario tiene `AdminSmall`, `VisualSmall` o `SuperAdmin`.
3. `GET /small/lagoons` devuelve `small_sim`.
4. El collector envia `product_type: "small"` o no envia producto.
5. `WS /ws/small/small_sim` recibe `tick`.
6. El frontend tiene `src/assets/positions/small_sim.json`.
