# Changelog de Documentacion

## v1.2.0 - 2026-03-13

Cambios documentados en esta version:

- Seguridad de ingest actualizada:
  - `POST /ingest/scada` requiere header `x-api-key`.
  - Campo de entrada alineado a codigo: `timestamp` (opcional), no `ts`.
  - Timeout configurable por `INGEST_TIMEOUT_SEC` y respuesta `504` en timeout.
- Autenticacion y JWT:
  - `POST /auth/login` documentado como flujo oficial.
  - Claims soportadas: `sub`, `email`, `roles`, `role`.
- RBAC multi-producto documentado:
  - Roles: `AdminCrystal`, `VisualCrystal`, `AdminSmall`, `VisualSmall`.
  - Permisos por laguna: `can_view`, `can_edit`, `can_control`.
  - Endpoints: `GET /lagoons`, `PUT /lagoons/{id}`, `POST /control/pump`.
- APIs por producto agregadas a la documentacion:
  - `GET /api/crystal/*`
  - `GET/POST/PUT/DELETE /api/small/*`
  - Layout y tags de Crystal documentados como endpoints de configuracion.
- WebSocket con control de permisos:
  - Endpoints activos: `/ws/scada`, `/ws/scada/{lagoon_id}`, `/ws/crystal/{lagoon_id}`, `/ws/small/{lagoon_id}`.
  - Token aceptado por query `token` o header `Authorization: Bearer ...`.
- Realtime payload actualizado:
  - Se agregan `plc_status`, `local_time`, `timezone`.
  - `start_ts` ahora se expone como string unico por laguna.
- Setup tecnico alineado a scripts actuales:
  - `scripts/sql/create_rbac_tables.sql`
  - `scripts/seed_roles.py`
  - `scripts/sql/create_scada_continuous_aggregates.sql`
- Limpieza general de texto:
  - Se removio contenido corrupto por codificacion en los documentos de `docs/`.

## v1.1.0 - 2026-02-25

- Nuevo endpoint de eventos de bombas:
  - `GET /scada/{lagoon_id}/pump-events/last-3`
- Script de agregados continuos:
  - `scripts/sql/create_scada_continuous_aggregates.sql`
- Historico con estrategia `view` o fallback `table`.

## v1.0.0 - 2026-02-09

- Base inicial de documentacion del backend SCADA.
- Endpoints de ingest, lectura, historial y websocket.
- Arquitectura general, flujo de insercion y guia tecnica.
