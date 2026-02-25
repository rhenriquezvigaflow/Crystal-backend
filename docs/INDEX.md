# Documentacion Crystal Lagoons Backend

**Version de documentacion:** `1.1`  
**Ultima actualizacion:** `2026-02-25`

---

## Punto de entrada recomendado

1. [ONE_PAGE_SUMMARY.md](./ONE_PAGE_SUMMARY.md) - Vista ejecutiva en 1 pagina.
2. [ARQUITECTURA_Y_FLUJO.md](./ARQUITECTURA_Y_FLUJO.md) - Arquitectura y contratos principales.
3. [FLUJO_INSERCION.md](./FLUJO_INSERCION.md) - Flujo operativo de ingest, WS y persistencia.
4. [GUIA_TECNICA_DESARROLLO.md](./GUIA_TECNICA_DESARROLLO.md) - Guia practica para implementar cambios.
5. [DIAGRAMAS_FLUJOS.md](./DIAGRAMAS_FLUJOS.md) - Diagramas ASCII de flujos y runtime.
6. [ONBOARDING.md](./ONBOARDING.md) - Ruta guiada para nuevos integrantes.

---

## Cambios v1.1 (2026-02-25)

Revisados y registrados en documentacion:

- Endpoint de eventos de bombas:
  - `GET /scada/{lagoon_id}/pump-events/last-3`
  - Fuente: `vw_scada_last_3_pump_actions` filtrada por `lagoon_id`.
- Historico con agregados continuos:
  - Script: `scripts/sql/create_scada_continuous_aggregates.sql`
  - Vistas: `public.scada_minute_hourly`, `public.scada_minute_daily`, `public.scada_minute_weekly`
  - Politicas: `add_continuous_aggregate_policy(...)`
- Flujo de historico documentado:
  - Primero consulta vistas continuas.
  - Si no existen, usa fallback sobre `scada_minute`.

Detalle completo:
- [CHANGELOG.md](./CHANGELOG.md)

---

## Endpoints documentados (estado actual)

- `POST /ingest/scada`
- `GET /scada/history/{resolution}`
- `GET /scada/{lagoon_id}/pump-events/last-3`
- `WS /ws/scada?lagoon_id=<lagoon_id>`

Nota:
- El router de historial usa `resolution` como segmento de ruta (`hourly|daily|weekly`).
- El websocket activo en `app/main.py` usa query param `lagoon_id`.

---

## Checklist rapido de sincronia doc-codigo

- [x] Nuevo endpoint de eventos registrado en arquitectura, guia tecnica y resumen.
- [x] Script SQL de agregados continuos registrado en setup y onboarding.
- [x] Flujo de historico (view/fallback) registrado en arquitectura y flujo.
- [x] Version documental incrementada a `1.1`.

