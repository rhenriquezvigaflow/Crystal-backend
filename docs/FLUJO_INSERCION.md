# Flujo de Insercion y Publicacion SCADA

**Version doc:** 1.1  
**Actualizado:** 2026-02-25

---

## 1) Flujo principal de ingest

Endpoint de entrada:
- `POST /ingest/scada`

Secuencia:

1. El cliente SCADA envia `{ lagoon_id, timestamp?, tags }`.
2. `ingest_scada` normaliza timestamp UTC.
3. Se persiste en BD mediante `ingest_service.ingest(...)`.
4. Se actualiza estado en memoria (`RealtimeStateStore`).
5. Se hace broadcast WS a clientes suscritos de la laguna.
6. Respuesta HTTP: `{"ok": true}`.

---

## 2) Estado en memoria y bootstrap

En arranque (`lifespan`):

1. Carga `timezone` de cada laguna desde `lagoons`.
2. Detecta lagunas con eventos en `scada_event`.
3. Precarga `pump_last_on` usando repositorio de eventos.

Consulta de precarga (repositorio):
- Vista: `vw_scada_last_3_pump_actions`
- Filtro: `lagoon_id = :lagoon_id`

Objetivo:
- Recuperar ultimo `start_local` por bomba/tag para estado inicial.

---

## 3) Endpoint de eventos recientes de bombas

Endpoint:
- `GET /scada/{lagoon_id}/pump-events/last-3`

Contrato:
- Respuesta `{"lagoon_id": "...", "events": [...]}`.
- Cada evento incluye:
  - `tag_id`
  - `tag_label`
  - `start_local`

Fuente de datos:
- `vw_scada_last_3_pump_actions` (filtrada por `lagoon_id`).

Uso recomendado:
- Tarjetas/listas de actividad reciente en frontend.

---

## 4) Flujo de historico agregado

Endpoint:
- `GET /scada/history/{resolution}`
- `resolution`: `hourly | daily | weekly`

Parametros:
- `lagoon_id`, `start_date`, `end_date`, `tags?`

Estrategia backend:

1. Verifica si existe vista continua de esa resolucion.
2. Si existe, consulta vista (`source = "view"`).
3. Si no existe, calcula con `time_bucket` sobre `scada_minute` (`source = "table"`).

---

## 5) Vistas continuas (TimescaleDB)

Script versionado:
- `scripts/sql/create_scada_continuous_aggregates.sql`

Crea:
- `public.scada_minute_hourly`
- `public.scada_minute_daily`
- `public.scada_minute_weekly`

Incluye politicas:
- `add_continuous_aggregate_policy(...)` por cada vista.

Comando de aplicacion:

```bash
psql "$DATABASE_URL" -f scripts/sql/create_scada_continuous_aggregates.sql
```

---

## 6) WebSocket operativo

Endpoint WS activo:
- `ws://<host>/ws/scada?lagoon_id=<lagoon_id>`

Mensajes:
- `snapshot` al conectar.
- `tick` en cada ingest.

