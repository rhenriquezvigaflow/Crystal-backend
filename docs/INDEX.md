# Documentacion Crystal Lagoons Backend

**Version de documentacion:** `1.2`
**Ultima actualizacion:** `2026-03-13`

---

## Punto de entrada recomendado

1. [ONE_PAGE_SUMMARY.md](./ONE_PAGE_SUMMARY.md) - Vista rapida del sistema actual.
2. [ARQUITECTURA_Y_FLUJO.md](./ARQUITECTURA_Y_FLUJO.md) - Arquitectura, seguridad y contratos.
3. [FLUJO_INSERCION.md](./FLUJO_INSERCION.md) - Flujo operacional de ingest, estado y websocket.
4. [GUIA_TECNICA_DESARROLLO.md](./GUIA_TECNICA_DESARROLLO.md) - Setup local, ejemplos y troubleshooting.
5. [DIAGRAMAS_FLUJOS.md](./DIAGRAMAS_FLUJOS.md) - Diagramas ASCII simplificados.
6. [ONBOARDING.md](./ONBOARDING.md) - Ruta de onboarding tecnico.

---

## Cambios v1.2 (2026-03-13)

Actualizado en documentacion:

- Seguridad de ingest por `x-api-key`.
- Flujo de login por `POST /auth/login` y uso de JWT bearer.
- RBAC por roles y permisos por laguna (`can_view`, `can_edit`, `can_control`).
- Endpoints producto-especificos (`/api/crystal/*`, `/api/small/*`).
- WebSockets autenticados con token y control por laguna.
- Setup de BD con tablas RBAC (`create_rbac_tables.sql`) y seed de roles.
- Correccion de codificacion de documentos.

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
- [x] Version documental incrementada a `1.2`.
