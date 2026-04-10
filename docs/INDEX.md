# Documentacion Crystal Lagoons Backend

**Version de documentacion:** `1.4.0`
**Ultima actualizacion:** `2026-04-09`

---

## Punto de entrada recomendado

1. [ONE_PAGE_SUMMARY.md](./ONE_PAGE_SUMMARY.md) - Resumen rapido del sistema actual.
2. [ARQUITECTURA_Y_FLUJO.md](./ARQUITECTURA_Y_FLUJO.md) - Arquitectura, seguridad, APIs y modelo de datos.
3. [ARQUITECTURA_END_TO_END_COLLECTOR_BACKEND.md](./ARQUITECTURA_END_TO_END_COLLECTOR_BACKEND.md) - Flujo collector -> backend -> frontend.
4. [FLUJO_INSERCION.md](./FLUJO_INSERCION.md) - Ingest, realtime, historico y layouts SCADA.
5. [GUIA_TECNICA_DESARROLLO.md](./GUIA_TECNICA_DESARROLLO.md) - Setup local, pruebas y troubleshooting.
6. [ONBOARDING.md](./ONBOARDING.md) - Ruta para integrarse al proyecto.
7. [README_ALARM_THRESHOLDS_API.md](./README_ALARM_THRESHOLDS_API.md) - Contrato de umbrales PT/FIT.
8. [ALARMAS_ACTUALES_Y_LOGICA.md](./ALARMAS_ACTUALES_Y_LOGICA.md) - Motor de alarmas y reglas operativas.
9. [DIAGRAMAS_FLUJOS.md](./DIAGRAMAS_FLUJOS.md) - Diagramas ASCII simplificados.
10. [CHANGELOG.md](./CHANGELOG.md) - Cambios historicos.

---

## Cambios v1.4.0

- Nuevo sistema SCADA layout dinamico:
  - tabla `layouts` para estructura visual reutilizable.
  - tabla `lagoon_layout_mapping` para mapping por laguna.
  - endpoints `GET /layouts/{layout_id}` y `GET|PUT /lagoons/{lagoon_id}/mapping`.
  - endpoints producto `GET|PUT /api/{product}/lagoons/{lagoon_id}/layout-config`.
- `mapping_json` reemplaza el enfoque anterior por `device_code` plano.
- `collector_tags` se expone junto al mapping para que el frontend muestre solo tags habilitados por collector.
- Cache in-memory de layouts y mappings con `SCADA_LAYOUT_CACHE_TTL_SEC` o `LAYOUT_CONFIG_CACHE_TTL_SEC`.
- El historico de producto responde `series[{tag, points}]`; el frontend acepta `tag`, `tag_key` o `name`.
- El layout SCADA se normaliza con alias `layout_small -> layout3`.
- `RETRO_SCADA` se mantiene como card/equipo siempre visible mediante `always_visible`.

---

## Endpoints documentados

Publicos:

- `GET /health`
- `POST /auth/login`

Ingest:

- `POST /ingest/scada` (requiere header `x-api-key`)

SCADA general:

- `GET /scada/{lagoon_id}/last-minute`
- `GET /scada/{lagoon_id}/current`
- `GET /scada/{lagoon_id}/pump-events/last-3`
- `GET /scada/history/{resolution}` (`hourly|daily|weekly`)

Layouts SCADA:

- `GET /layouts/{layout_id}`
- `GET /api/layouts/{layout_id}`
- `GET /lagoons/{lagoon_id}/mapping`
- `GET /api/lagoons/{lagoon_id}/mapping`
- `PUT /lagoons/{lagoon_id}/mapping`
- `PUT /api/lagoons/{lagoon_id}/mapping`

Producto Crystal:

- `GET /api/crystal/lagoons`
- `GET /api/crystal/dashboard`
- `GET /api/crystal/lagoons/{lagoon_id}/last-minute`
- `GET /api/crystal/lagoons/{lagoon_id}/current`
- `GET /api/crystal/lagoons/{lagoon_id}/pump-events/last-3`
- `GET /api/crystal/history`
- `GET|PUT /api/crystal/lagoons/{lagoon_id}/layout-config`

Producto Small:

- `GET /api/small/lagoons`
- `GET /api/small/dashboard`
- `GET /api/small/lagoons/{lagoon_id}/last-minute`
- `GET /api/small/lagoons/{lagoon_id}/current`
- `GET /api/small/lagoons/{lagoon_id}/pump-events/last-3`
- `GET /api/small/history`
- `GET|PUT /api/small/lagoons/{lagoon_id}/layout-config`
- `POST|PUT /api/small/control`
- `GET|POST|DELETE /api/small/chemicals`

Alarmas PT/FIT:

- `GET /alarms/{lagoon_id}/thresholds/pt-fit/view`
- `PUT /alarms/{lagoon_id}/thresholds/pt-fit`
- aliases con `/crystal`, `/small`, `/api`, `/api/crystal` y `/api/small`.

WebSocket:

- `WS /ws/scada?lagoon_id=<id>&token=<jwt>`
- `WS /ws/scada/{lagoon_id}?token=<jwt>`
- `WS /ws/crystal/{lagoon_id}?token=<jwt>`
- `WS /ws/small/{lagoon_id}?token=<jwt>`

---

## Checklist doc-codigo

- [x] Ingest por API key documentado.
- [x] RBAC por laguna documentado.
- [x] WebSocket autenticado documentado.
- [x] Historico y respuesta `series` documentados.
- [x] Layout dinamico `layouts` + `lagoon_layout_mapping` documentado.
- [x] Filtro por `collector_tags` documentado.
- [x] Contrato de umbrales PT/FIT documentado.
