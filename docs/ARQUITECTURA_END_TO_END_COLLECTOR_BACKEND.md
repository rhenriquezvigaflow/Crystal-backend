# Arquitectura End-to-End (Collector -> Backend -> Frontend SCADA)

**Version doc:** 1.3.0
**Actualizado:** 2026-04-24
**Audiencia:** backend, frontend, integracion SCADA y soporte

---

## 1) Objetivo

Explicar el flujo completo desde PLC/collector hasta la UI SCADA:

- ingest realtime,
- persistencia historica,
- alarmas,
- WebSocket,
- layouts reutilizables,
- mappings por laguna,
- estados SVG y tarjetas KPI.

---

## 2) Repos y responsabilidades

### Collector

Responsable de:

- conectarse a PLCs,
- leer tags por ciclo,
- normalizar payload,
- enviar `POST /ingest/scada`,
- mantener spool local si falla backend.

### Backend

Responsable de:

- autenticar ingest con API key,
- persistir historico y eventos,
- evaluar alarmas,
- exponer REST y WS,
- resolver layouts/mappings SCADA,
- exponer tags habilitados por collector.

### Frontend

Responsable de:

- autenticar usuario,
- aplicar RBAC de UI,
- cargar layout y mapping,
- mezclar layout + mapping + realtime,
- renderizar SVG, tarjetas KPI, labels y estados de bombas/valvulas,
- mostrar historico.

---

## 3) Flujo alto nivel

```text
PLC
  -> Collector
  -> POST /ingest/scada
  -> Backend
      -> scada_event / scada_minute
      -> alarm_event / notifications
      -> RealtimeStateStore
      -> WS tick
      -> layouts + lagoon_layout_mapping
  -> Frontend
      -> GET /api/{product}/lagoons
      -> GET /lagoons/{lagoon_id}/mapping
      -> GET /layouts/{layout_id}
      -> WS /ws/scada/{lagoon_id}
      -> SVG + overlays
```

---

## 4) Ingest collector -> backend

Payload:

```json
{
  "lagoon_id": "costa_del_lago",
  "timestamp": "2026-04-09T18:20:00+00:00",
  "tags": {
    "PT117_R_SCADA": 2.31,
    "P006_STS_SCADA": 1
  }
}
```

Header:

- `x-api-key: <COLLECTOR_API_KEY>`

Backend:

1. valida API key.
2. persiste en `scada_event` y `scada_minute`.
3. evalua alarmas.
4. actualiza estado realtime.
5. emite WebSocket `tick`.

---

## 5) Layout SCADA reutilizable

La UI no debe duplicar SVGs por laguna. El sistema separa:

1. `layouts.json_definition`: estructura visual y posiciones.
2. `lagoon_layout_mapping.mapping_json`: tags/labels/svg_target por laguna.
3. `collector_tag_registry`: tags realmente habilitados por collector.
4. WebSocket `tags`: valores realtime.

Ejemplo `layout`:

```json
{
  "id": "pressure_1",
  "type": "kpi",
  "fallback_tag": "PT117_R_SCADA",
  "unit": "bar",
  "position": { "x": 0.213, "y": 0.403 }
}
```

Ejemplo `mapping_json`:

```json
{
  "pressure_1": {
    "tag": "PT117_R_SCADA",
    "label": "PT_117"
  }
}
```

Reglas:

- si `mapping_json[element_id].tag` existe, gana sobre `fallback_tag`.
- si `mapping_json[element_id].label` existe, gana sobre `default_label`.
- `collector_tags` filtra tarjetas no disponibles para esa laguna.
- `always_visible=true` permite tarjetas como `RETRO_SCADA` aunque no haya tag realtime.

---

## 6) Estados de bombas y valvulas

Los estados discretos son:

- `0`: rojo.
- `1`: verde.
- `2`: azul.
- `3`: amarillo.
- sin dato: gris.

Backend no pinta el SVG. El frontend aplica el color sobre los nodos por `svg_target`.

Configuracion frontend:

- `src/scada/equipment-state/layouts/layout1.equipment.json`
- `src/scada/equipment-state/layouts/layout2.equipment.json`
- `src/scada/equipment-state/layouts/layout3.equipment.json`

Entradas con `tag` son dinamicas; entradas con `state` son fijas.

---

## 7) Historico

Backend:

- `GET /scada/history/{resolution}`
- `GET /api/crystal/history`
- `GET /api/small/history`

Resolucion:

- `hourly`
- `daily`
- `weekly`

Respuesta:

```json
{
  "lagoon_id": "costa_del_lago",
  "resolution": "hourly",
  "source": "table",
  "series": [
    {
      "tag": "PT117_R_SCADA",
      "points": [
        { "timestamp": "2026-04-09T12:00:00Z", "value": 2.34 }
      ]
    }
  ]
}
```

Frontend:

- acepta `tag`, `tag_key` o `name`, para compatibilidad.
- muestra selector multi TAG.
- filtra tags de estado, `RETRO` y totalizadores `WM`.

---

## 8) Modo desconectado

Si la laguna no tiene conexion realtime:

- el frontend espera hasta 7 segundos por tags realtime,
- luego muestra el mapa igualmente,
- muestra tarjetas con `--`,
- mantiene nombres y posiciones desde BD.

Esto permite ver `central_district_dubai` y otras lagunas offline sin depender del collector activo.

---

## 9) Donde tocar codigo

Backend layout:

- `app/layout_config/service.py`
- `app/layout_config/repository.py`
- `app/routers/scada_layouts.py`
- `app/routers/crystal/lagoons.py`
- `app/routers/small/lagoons.py`
- `app/models/layout.py`
- `app/models/lagoon_layout_mapping.py`

Frontend layout:

- `src/hooks/useScadaLayoutScene.ts`
- `src/api/scadaLayoutsApi.ts`
- `src/scada/layoutSceneResolver.ts`
- `src/components/lagoon/ScadaMapPanel.tsx`
- `src/containers/ScadaOverlay.tsx`
- `src/containers/ScadaEquipmentStateOverlay.tsx`
- `src/scada/equipment-state/layouts/*.equipment.json`
- `src/scada/labels/layouts/*.base.json`

Alarmas:

- `app/alarms/*`
- `app/alarms/thresholds/*`
- `src/components/AlarmManagerModal.tsx`
- `src/hooks/useAlarmThresholds.ts`

---

## 10) Validacion recomendada

Backend:

```bash
python -m pytest -q
```

Frontend:

```bash
npm run build
```

---

## 11) Alta de una nueva laguna

La guia operativa actualizada vive en:

- [FLUJO_INSERCION.md](./FLUJO_INSERCION.md#11-alta-de-una-nueva-planta-o-laguna)

Resumen corto del proceso:

1. crear la laguna en `lagoons`;
2. reutilizar o crear el layout en `layouts`;
3. cargar `mapping_json` por API (`PUT /api/{product}/lagoons/{lagoon_id}/layout-config`) o por SQL;
4. registrar tags en `collector_tag_registry`;
5. verificar permisos en `vw_user_lagoons`;
6. reiniciar backend si hubo alta o cambio directo de metadata base;
7. probar `POST /ingest/scada`, `GET /api/{product}/lagoons`, `GET /api/{product}/lagoons/{lagoon_id}/layout-config` y `WS /ws/scada/{lagoon_id}`.

La decision de dejar el detalle en un solo documento evita que la arquitectura y la guia operativa se desalineen.
