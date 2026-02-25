# Changelog de Documentacion

## v1.1.0 - 2026-02-25

Cambios documentados en esta version:

- Nuevo endpoint de eventos de bombas:
  - `GET /scada/{lagoon_id}/pump-events/last-3`
  - Fuente: `vw_scada_last_3_pump_actions` filtrada por `lagoon_id`.
- Repositorio de eventos actualizado:
  - `ScadaEventRepository.get_last_3_events_by_lagoon(...)`
  - `ScadaEventRepository.get_last_event_time_by_lagoon(...)` alineado a la vista.
- Script SQL versionado para agregados continuos:
  - `scripts/sql/create_scada_continuous_aggregates.sql`
  - Crea:
    - `public.scada_minute_hourly`
    - `public.scada_minute_daily`
    - `public.scada_minute_weekly`
  - Incluye políticas `add_continuous_aggregate_policy(...)`.
- Flujo de historico actualizado en documentacion:
  - Preferencia por vistas continuas.
  - Fallback a consulta directa sobre `scada_minute` cuando la vista no existe.
- Documentacion de setup actualizada:
  - Comando para aplicar agregados continuos en base de datos.

## v1.0.0 - 2026-02-09

- Base inicial de documentacion del backend SCADA.
- Endpoints de ingest, lectura, historial y websocket.
- Arquitectura general, flujo de insercion y guias de desarrollo.
