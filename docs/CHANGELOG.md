# Changelog de Documentacion

## v1.3.4 - 2026-04-07

Cambios documentados en esta version:

- Nuevo documento de arquitectura completa para onboarding:
  - `docs/ARQUITECTURA_END_TO_END_COLLECTOR_BACKEND.md`
- Cubre flujo de punta a punta:
  - collector (lectura PLC, cola, sender, spool)
  - backend (ingest, estado realtime, persistencia, alarmas)
  - APIs REST, WebSocket, seguridad y modelo de datos.
- `INDEX.md` actualizado para enlazar este documento como entrada oficial.

## v1.3.3 - 2026-04-07

Cambios documentados en esta version:

- Sincronizacion completa de carpeta `docs/` con contrato vigente de umbrales PT/FIT.
- `INDEX.md` actualizado a version documental `1.3.3` con referencias directas a:
  - `README_ALARM_THRESHOLDS_API.md`
  - `ALARMAS_ACTUALES_Y_LOGICA.md`
  - `PROMPT_FRONT_ALARMAS_PT_FIT.md`
- `PROMPT_FRONT_ALARMAS_PT_FIT.md` reescrito al flujo actual:
  - lectura por `GET /alarms/{lagoon_id}/thresholds/pt-fit/view`
  - escritura por `PUT /alarms/{lagoon_id}/thresholds/pt-fit`
  - `severity` unico, sin `deadband`, sin endpoints legacy de lectura.
- Registro del ajuste SQL para evitar error PostgreSQL `42P16` al cambiar columnas de vista:
  - uso de `DROP VIEW IF EXISTS ...` + `CREATE VIEW ...` en migraciones de `2026-04-07`.

## v1.3.2 - 2026-04-07

Cambios documentados en esta version:

- UI/API de umbrales PT/FIT simplificada:
  - `severity` unico por tag.
  - `deadband` deja de ser parte del contrato de umbrales.
  - estado por tag en UI: `Configurada` / `Sin Configurar`.
- Backend de umbrales:
  - `GET /alarms/{lagoon_id}/thresholds/pt-fit/view` responde `severity` unico.
  - `PUT /alarms/{lagoon_id}/thresholds/pt-fit` recibe `severity` unico.
  - `deadband` se fija internamente en `0.0` para definiciones `threshold`.
  - vista SQL consolidada actualizada para source `configured|candidate`.

## v1.3.1 - 2026-04-07

Cambios documentados en esta version:

- Alarmas PT/FIT:
  - Se eliminan endpoints legacy de lectura:
    - `GET /alarms/{lagoon_id}/thresholds/pt-fit/candidates`
    - `GET /alarms/{lagoon_id}/thresholds/pt-fit`
  - Se mantiene como contrato vigente:
    - `GET /alarms/{lagoon_id}/thresholds/pt-fit/view`
    - `PUT /alarms/{lagoon_id}/thresholds/pt-fit`
  - Alias `crystal/small` y variantes `/api` aplican solo para `view` y `put`.

## v1.3.0 - 2026-04-06

Cambios documentados en esta version:

- Alarmas de umbral PT/FIT:
  - Endpoints activos:
    - `GET /alarms/{lagoon_id}/thresholds/pt-fit/candidates`
    - `GET /alarms/{lagoon_id}/thresholds/pt-fit`
    - `PUT /alarms/{lagoon_id}/thresholds/pt-fit`
  - Aliases de compatibilidad agregados:
    - `GET/PUT /crystal/alarms/{lagoon_id}/thresholds/pt-fit...`
    - `GET/PUT /small/alarms/{lagoon_id}/thresholds/pt-fit...`
- Separacion por capas del modulo:
  - `app/alarms/thresholds/schemas.py`
  - `app/alarms/thresholds/service.py`
  - `app/alarms/thresholds/repository.py`
- Validaciones funcionales backend para frontend:
  - `tag_id` inicia en `PT` o `FIT`
  - `items` no vacio
  - `min_value` o `max_value` obligatorio
  - `min_value < max_value` cuando ambos existen
  - severidades permitidas: `info|warning|critical`
  - `deadband >= 0`
- Guia operativa agregada:
  - `docs/README_ALARM_THRESHOLDS_API.md` con rutas finales y ejemplos `curl`.

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
