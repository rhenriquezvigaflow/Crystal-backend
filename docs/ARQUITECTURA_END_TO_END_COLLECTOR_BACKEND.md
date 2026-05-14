# Arquitectura End-to-End (Collector -> Backend -> Frontend SCADA)

**Version doc:** 2.0.0  
**Actualizado:** 2026-04-27  
**Audiencia:** backend, frontend, integracion SCADA y soporte

## 1. Objetivo

Explicar el flujo completo desde PLC/collector hasta la UI SCADA:

- ingest realtime;
- persistencia historica;
- alarmas;
- WebSocket;
- escenas visuales locales;
- estados SVG y tarjetas KPI.

## 2. Repos y Responsabilidades

### Collector

Responsable de conectarse a PLCs, leer tags por ciclo, enviar `POST /ingest/scada` y mantener spool local si falla backend.

### Backend

Responsable de autenticar ingest, persistir historico/eventos, evaluar alarmas, exponer REST/WS, resolver permisos y enviar notificaciones.

### Frontend

Responsable de autenticar usuario, aplicar RBAC de UI, cargar escena local por laguna, mezclar escena + realtime y renderizar SVG, KPIs, labels, estados, historico y alarmas.

## 3. Flujo Alto Nivel

```text
PLC
  -> Collector
  -> POST /ingest/scada
  -> Backend
      -> scada_event / scada_minute
      -> alarm_event / notifications
      -> RealtimeStateStore
      -> WS tick
  -> Frontend
      -> GET /api/lagoons
      -> src/assets/positions/{lagoon_id}.json
      -> WS /ws/scada/{lagoon_id}
      -> GET /api/scada/{lagoon_id}/history
      -> SVG + overlays
```

## 4. Ingest Collector -> Backend

Payload:

```json
{
  "lagoon_id": "costa_del_lago",
  "timestamp": "2026-04-27T18:20:00+00:00",
  "tags": {
    "PT117_R_SCADA": 2.31,
    "P006_STS_SCADA": 1
  }
}
```

Header:

- `X-Api-Key: <COLLECTOR_API_KEY>`

Backend:

1. valida API key;
2. sincroniza tags/alarms si existe la funcion SQL opcional;
3. persiste en `scada_event` y `scada_minute`;
4. evalua alarmas;
5. actualiza estado realtime;
6. emite WebSocket `tick`.

## 5. Escena SCADA Local

La UI no depende de endpoints de layout. El sistema separa:

1. SVG React en `src/svg/layout*.tsx`.
2. Registro en `src/scada/svgRegistry.ts`.
3. Escena por laguna en `src/assets/positions/*.json`.
4. WebSocket `tags`: valores realtime.

Ejemplo:

```json
{
  "lagoon_id": "ary",
  "layout_id": "layout2",
  "svg_component": "layout2",
  "kpis": [
    {
      "tag": "PT117_R",
      "label": "PT_117",
      "position": { "top": "29%", "left": "37.4%" }
    }
  ],
  "pumps": [
    {
      "tag": "P005_ST",
      "label": "Bomba Filtro",
      "svg_target": "circle26-4",
      "panel": "pump-status"
    }
  ]
}
```

Reglas:

- `tag` debe coincidir con el nombre enviado por collector.
- `svg_target` debe existir como ID dentro del SVG.
- `panel: "pump-status"` hace que la bomba aparezca en el panel de eventos.
- `always_visible=true` permite mostrar elementos aunque no haya dato realtime.

## 6. Estados de Bombas y Valvulas

Los estados discretos son:

- `0`: rojo.
- `1`: verde.
- `2`: azul.
- `3`: amarillo.
- sin dato: gris.

Backend no pinta el SVG. El frontend aplica el color sobre los nodos por `svg_target`.

## 7. Historico

Backend:

- `GET /scada/{lagoon_id}/history`

Resolucion:

- `hourly`
- `daily`
- `weekly`

## 8. Modo Desconectado

Si la laguna no tiene conexion realtime:

- el frontend espera hasta 7 segundos por tags realtime;
- luego muestra el mapa igualmente;
- muestra tarjetas con `--`;
- mantiene nombres y posiciones desde el JSON local.

## 9. Donde Tocar Codigo

Backend:

- `app/routers/ingest.py`
- `app/routers/scada.py`
- `app/routers/events.py`
- `app/routers/websocket.py`
- `app/auth/services/lagoon_service.py`
- `app/alarms/*`
- `app/alarms/thresholds/*`

Frontend layout/escena:

- `src/assets/positions/*.json`
- `src/hooks/useScadaLayoutScene.ts`
- `src/scada/lagoonSceneBundle.ts`
- `src/components/lagoon/ScadaMapPanel.tsx`
- `src/containers/ScadaOverlay.tsx`
- `src/containers/ScadaEquipmentStateOverlay.tsx`
- `src/scada/svgRegistry.ts`

Collector:

- `collector_python/collectors.yml`
- `collector_python/config/*.yml`

## 10. Validacion Recomendada

Backend:

```powershell
python -m pytest -q
```

Frontend:

```powershell
npm run build
```

Collector:

```powershell
python main.py --config collectors.yml
```

## 11. Alta de una Nueva Laguna

La guia operativa actualizada vive en:

- [FLUJO_INSERCION.md](./FLUJO_INSERCION.md#10-alta-de-una-nueva-planta-o-laguna)
