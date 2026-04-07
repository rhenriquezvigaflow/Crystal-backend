# Documentacion Crystal Lagoons Backend

**Version de documentacion:** `1.3.3`
**Ultima actualizacion:** `2026-04-07`

---

## Punto de entrada recomendado

1. [ONE_PAGE_SUMMARY.md](./ONE_PAGE_SUMMARY.md) - Vista rapida del sistema actual.
2. [ARQUITECTURA_Y_FLUJO.md](./ARQUITECTURA_Y_FLUJO.md) - Arquitectura, seguridad y contratos.
3. [FLUJO_INSERCION.md](./FLUJO_INSERCION.md) - Flujo operacional de ingest, estado y websocket.
4. [GUIA_TECNICA_DESARROLLO.md](./GUIA_TECNICA_DESARROLLO.md) - Setup local, ejemplos y troubleshooting.
5. [DIAGRAMAS_FLUJOS.md](./DIAGRAMAS_FLUJOS.md) - Diagramas ASCII simplificados.
6. [ONBOARDING.md](./ONBOARDING.md) - Ruta de onboarding tecnico.
7. [README_ALARM_THRESHOLDS_API.md](./README_ALARM_THRESHOLDS_API.md) - Contrato vigente de umbrales PT/FIT (`GET /view` + `PUT`).
8. [ALARMAS_ACTUALES_Y_LOGICA.md](./ALARMAS_ACTUALES_Y_LOGICA.md) - Estado real del motor de alarmas y reglas operativas.
9. [PROMPT_FRONT_ALARMAS_PT_FIT.md](./PROMPT_FRONT_ALARMAS_PT_FIT.md) - Prompt frontend actualizado al contrato actual.

---

## Cambios v1.3.3 (2026-04-07)

Actualizado en documentacion:

- Contrato PT/FIT consolidado:
  - `GET /alarms/{lagoon_id}/thresholds/pt-fit/view`
  - `PUT /alarms/{lagoon_id}/thresholds/pt-fit`
- Contrato simplificado de umbrales:
  - `severity` unico por tag.
  - `deadband` fuera del contrato API (interno fijo en `0.0`).
  - `source` en vista: `configured|candidate`.
- Prompt frontend de alarmas alineado a implementacion actual.
- Registro de ajuste de migracion SQL para recreacion de vista sin error `42P16`.

Detalle completo:
- [CHANGELOG.md](./CHANGELOG.md)

---

## Endpoints documentados (estado actual)

Publicos:

- `GET /health`
- `POST /auth/login`

Ingest:

- `POST /ingest/scada` (requiere `x-api-key`)

SCADA general (bearer + rol de lectura):

- `GET /scada/{lagoon_id}/last-minute`
- `GET /scada/{lagoon_id}/current`
- `GET /scada/{lagoon_id}/pump-events/last-3`
- `GET /scada/history/{resolution}`

RBAC por permisos de laguna:

- `GET /lagoons`
- `PUT /lagoons/{id}`
- `POST /control/pump`

Producto Crystal:

- `GET /api/crystal/lagoons`
- `GET /api/crystal/dashboard`
- `GET /api/crystal/lagoons/{lagoon_id}/last-minute`
- `GET /api/crystal/lagoons/{lagoon_id}/current`
- `GET /api/crystal/lagoons/{lagoon_id}/pump-events/last-3`
- `GET /api/crystal/history`
- `GET|PUT|DELETE /api/crystal/layout`
- `GET|PUT|DELETE /api/crystal/tags`

Producto Small:

- `GET /api/small/lagoons`
- `GET /api/small/dashboard`
- `GET /api/small/lagoons/{lagoon_id}/last-minute`
- `GET /api/small/lagoons/{lagoon_id}/current`
- `GET /api/small/lagoons/{lagoon_id}/pump-events/last-3`
- `GET /api/small/history`
- `POST|PUT /api/small/control`
- `GET|POST|DELETE /api/small/chemicals`

WebSocket:

- `WS /ws/scada?lagoon_id=<id>&token=<jwt>`
- `WS /ws/scada/{lagoon_id}?token=<jwt>`
- `WS /ws/crystal/{lagoon_id}?token=<jwt>`
- `WS /ws/small/{lagoon_id}?token=<jwt>`

---

## Checklist rapido doc-codigo

- [x] Payload de ingest alineado (`timestamp` + `x-api-key`).
- [x] Autenticacion JWT y roles documentados.
- [x] RBAC de permisos por laguna documentado.
- [x] APIs Crystal y Small incluidas.
- [x] WebSockets con seguridad documentados.
- [x] Contrato PT/FIT vigente (`GET /view` + `PUT`) documentado.
- [x] Version documental incrementada a `1.3.3`.
