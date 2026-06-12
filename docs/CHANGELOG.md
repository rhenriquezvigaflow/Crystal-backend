# Changelog de Documentacion

## v2.1.0 - 2026-06-12

Cambios documentados:

- Se agrega `SMALL_LAGOONS.md` con endpoints, alta de `small_sim` y checklist.
- Se documenta `product_type` opcional en ingest y la validacion contra `lagoons.product_type`.
- Se actualizan rutas productizadas `/crystal/*`, `/small/*` y `WS /ws/{product_type}/{lagoon_id}`.
- Se incorpora `VisualSmall` en roles soportados.
- Se actualiza el flujo de alta de lagunas con ejemplos Crystal y Small.

## v2.0.0 - 2026-04-27

Cambios documentados:

- Documentacion realineada con los routers activos en `app/main.py`.
- Se retiran de la documentacion vigente las rutas de layout/mapping backend-driven no registradas.
- Se documenta que las escenas visuales SCADA viven en `crystal-frontend/src/assets/positions/*.json`.
- Se actualizan endpoints activos:
  - `GET /lagoons`
  - `POST /ingest/scada`
  - `GET /scada/{lagoon_id}/realtime`
  - `GET /scada/{lagoon_id}/history`
  - `GET /scada/{lagoon_id}/kpis`
  - `GET /scada/{lagoon_id}/events`
  - `GET /scada/{lagoon_id}/pump-events`
  - `GET /scada/{lagoon_id}/pump-events/last-3`
  - `GET /scada/{lagoon_id}/pump-events/report.xlsx`
  - `WS /ws/scada/{lagoon_id}`
  - `GET/PUT /alarms/{lagoon_id}/thresholds/pt-fit`
  - `POST /email/test-alert`
  - `/api/small/control`
  - `/api/small/chemicals`
- Se agrega la laguna `ary` al flujo documentado de collector/frontend.
- Se actualizan las guias de alta de laguna para usar `src/assets/positions/<lagoon_id>.json`.

## v1.4.0 - 2026-04-09

Version historica. Contenia documentacion de layout backend-driven y rutas por producto que ya no son la fuente vigente. Para contratos actuales usar:

- `../README.md`
- `ARQUITECTURA_Y_FLUJO.md`
- `FLUJO_INSERCION.md`
- `../../crystal-frontend/docs/API_CONTRACTS.md`
