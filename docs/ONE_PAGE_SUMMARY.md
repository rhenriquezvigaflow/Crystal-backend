# One-Page Summary - Crystal Lagoons Backend

**Version doc:** 1.4.0
**Actualizado:** 2026-04-09

---

## Arquitectura en 30 segundos

```text
SCADA Collector -- POST /ingest/scada + x-api-key --> FastAPI
                                                        |
                                                        +--> IngestService -> scada_event / scada_minute
                                                        +--> Alarm engine -> alarm_event / notifications
                                                        +--> RealtimeStateStore -> WebSocket tick
                                                        +--> LayoutConfigService -> layouts / lagoon_layout_mapping
                                                        +--> PostgreSQL
```

El backend expone:

- Login JWT (`POST /auth/login`).
- Lecturas SCADA (`/scada/*`).
- APIs por producto (`/api/crystal/*`, `/api/small/*`).
- Layout SCADA dinamico (`/layouts`, `/lagoons/{id}/mapping`, `/api/{product}/lagoons/{id}/layout-config`).
- Alarmas PT/FIT (`/alarms/{id}/thresholds/pt-fit`).
- WebSockets autenticados (`/ws/*`).

---

## Flujo principal ingest

1. Collector envia `{lagoon_id, timestamp?, tags}` a `POST /ingest/scada`.
2. Backend valida `x-api-key`.
3. `IngestService` persiste eventos y buckets por minuto.
4. Se evaluan alarmas.
5. Se actualiza `RealtimeStateStore`.
6. Se emite `tick` por WebSocket a la laguna.
7. Respuesta HTTP: `{"ok": true}`.

---

## Layout SCADA dinamico

Objetivo: reutilizar un mismo SVG/layout en varias lagunas, cambiando solo tags, labels y estados por mapping.

Tablas:

- `layouts`: define layout reutilizable en `json_definition`.
- `lagoon_layout_mapping`: define `mapping_json` por `(lagoon_id, layout_id)`.

Endpoints principales:

- `GET /layouts/{layout_id}`
- `GET /lagoons/{lagoon_id}/mapping`
- `PUT /lagoons/{lagoon_id}/mapping`
- `GET|PUT /api/{product}/lagoons/{lagoon_id}/layout-config`

`mapping_json`:

```json
{
  "pressure_1": { "tag": "PT117_R_SCADA", "label": "PT_117" },
  "pump_filtracion": { "tag": "P006_STS_SCADA", "label": "Bomba Filtracion" }
}
```

Reglas:

- Las claves del mapping deben existir en `layout.json_definition.elements[].id`.
- `collector_tags` se entrega al frontend para ocultar tarjetas cuyo tag no esta habilitado por collector.
- `always_visible=true` permite mostrar elementos como `RETRO_SCADA` aun sin dato realtime.
- Cache in-memory configurable con `SCADA_LAYOUT_CACHE_TTL_SEC` o `LAYOUT_CONFIG_CACHE_TTL_SEC`.

---

## Seguridad

Ingest:

- Header obligatorio: `x-api-key: <COLLECTOR_API_KEY>`.

API usuario:

- `Authorization: Bearer <token>`.
- Roles: `AdminCrystal`, `VisualCrystal`, `AdminSmall`, `VisualSmall`, `SuperAdmin`.
- Permisos por laguna desde `vw_user_lagoons`: `can_view`, `can_edit`, `can_control`.

WebSocket:

- Token por query `token=<jwt>` o header `Authorization`.
- Requiere `can_view` para la laguna.

---

## Base de datos clave

- `lagoons`: catalogo, timezone, `scada_layout`, `product_type`, `enable`.
- `layouts`: layout reusable y `json_definition`.
- `lagoon_layout_mapping`: mapping por laguna/layout.
- `collector_tag_registry`: tags habilitados por collector para cada laguna.
- `scada_event`: cambios de estado.
- `scada_minute`: valores historicos por minuto.
- `alarm_definition`, `alarm_event`, `alarm_notification_rule`.
- `users`, `roles`, `user_roles`.

Vistas:

- `vw_user_lagoons`.
- `vw_scada_last_3_pump_actions`.
- `scada_minute_hourly`, `scada_minute_daily`, `scada_minute_weekly` si existen.
- `vw_alarm_thresholds_pt_fit_lagoon`.

---

## Setup minimo

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Variables minimas:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/crystal
COLLECTOR_API_KEY=replace-me
JWT_SECRET_KEY=replace-me
```

---

Mas detalle:

- [ARQUITECTURA_Y_FLUJO.md](./ARQUITECTURA_Y_FLUJO.md)
- [GUIA_TECNICA_DESARROLLO.md](./GUIA_TECNICA_DESARROLLO.md)
- [FLUJO_INSERCION.md](./FLUJO_INSERCION.md)
