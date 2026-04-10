# Arquitectura End-to-End (Collector -> Backend -> Frontend SCADA)

**Version doc:** 1.2.0
**Actualizado:** 2026-04-09
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
  "position": { "left": "21.3%", "top": "40.3%" }
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

## 11) Paso a Paso: Inserción de una Nueva Laguna

Basado en la arquitectura end-to-end, aquí tienes un ejemplo detallado de cómo configurar e insertar una nueva laguna en el sistema Crystal Lagoons. Este proceso involucra la base de datos, configuración de layouts SCADA, mappings, permisos y bootstrap automático.

#### **Fase 1: Preparación de Datos en Base de Datos**

1. **Insertar la Laguna en la Tabla Principal (`lagoons`)**  
   Crea el registro base de la laguna con sus metadatos esenciales.  
   - **Campos clave**: `id` (ej: `'costa_del_lago'`), `name` (ej: `'Costa del Lago'`), `product_type` (`'crystal'` o `'small'`), `timezone` (ej: `'America/Argentina/Buenos_Aires'`), `scada_layout` (ej: `'layout1'`), `enable` (`true`), `plc_type` (opcional, ej: `'S7-1200'`), `ip` (opcional).  
   - **Ejemplo SQL**:
     ```sql
     INSERT INTO lagoons (id, name, product_type, timezone, scada_layout, enable, plc_type, ip)
     VALUES ('costa_del_lago', 'Costa del Lago', 'crystal', 'America/Argentina/Buenos_Aires', 'layout1', true, 'S7-1200', '192.168.1.100');
     ```
   - **Resultado**: La laguna queda registrada y habilitada para ingestión de datos.

2. **Crear o Reutilizar un Layout SCADA (`layouts`)**  
   Define la estructura visual (SVG y elementos) si no existe un layout reutilizable.  
   - **Campos**: `id` (ej: `'layout1'`), `name`, `json_definition` (JSON con elementos como tarjetas KPI, bombas, etc.).  
   - **Ejemplo de `json_definition`**:
     ```json
     {
       "elements": [
         {
           "id": "pressure_1",
           "type": "pressure",
           "label": "PT_117",
           "svg_target": "pt117_rect",
           "always_visible": false
         },
         {
           "id": "pump_status",
           "type": "pump",
           "label": "Bomba Principal",
           "svg_target": "pump_svg_id",
           "always_visible": true
         }
       ]
     }
     ```
   - **Nota**: Los layouts son reutilizables entre lagunas; solo crea uno nuevo si es necesario.

3. **Crear el Mapping entre Laguna y Layout (`lagoon_layout_mapping`)**  
   Mapea los elementos del layout a tags SCADA específicos de la laguna.  
   - **Campos**: `lagoon_id`, `layout_id`, `mapping_json` (JSON que asocia elementos a tags).  
   - **Ejemplo de `mapping_json`**:
     ```json
     {
       "pressure_1": {
         "tag": "PT117_R_SCADA",
         "label": "Presión PT117"
       },
       "pump_status": {
         "tag": "P006_STS_SCADA",
         "label": "Status Bomba"
       }
     }
     ```
   - **Ejemplo SQL**:
     ```sql
     INSERT INTO lagoon_layout_mapping (lagoon_id, layout_id, mapping_json)
     VALUES ('costa_del_lago', 'layout1', '{"pressure_1": {"tag": "PT117_R_SCADA", "label": "Presión PT117"}, "pump_status": {"tag": "P006_STS_SCADA"}}'::jsonb);
     ```
   - **Resultado**: El frontend puede renderizar el layout con datos reales de la laguna.

4. **Registrar Tags Habilitados del Collector (`collector_tag_registry`)**  
   Especifica qué tags el collector debe monitorear para esta laguna.  
   - **Campos**: `lagoon_id`, `tag_id` (ej: `'PT117_R_SCADA'`), `enabled` (`true`).  
   - **Ejemplo SQL**:
     ```sql
     INSERT INTO collector_tag_registry (lagoon_id, tag_id, enabled)
     VALUES
       ('costa_del_lago', 'PT117_R_SCADA', true),
       ('costa_del_lago', 'P006_STS_SCADA', true);
     ```
   - **Nota**: Esto filtra las tarjetas visibles en la UI; solo tags habilitados aparecen.

#### **Fase 2: Integración con Usuarios y Permisos**

5. **Asignar la Laguna a Usuarios (`user_lagoons` o roles)**  
   Vincula usuarios con permisos (`can_view`, `can_edit`, `can_control`) para acceder a la laguna.  
   - Usa roles como `AdminCrystal` o `VisualCrystal` para control de acceso.  
   - **Referencia**: El servicio `lagoon_service.py` maneja la lógica de permisos.

#### **Fase 3: Bootstrap y Estado Inicial (Automático en Startup)**

6. **Reiniciar el Backend para Precarga**  
   Al iniciar el backend (`app/main.py` en `lifespan`), se ejecuta automáticamente:  
   - Carga lagunas habilitadas desde `lagoons`.  
   - Precarga `timezone`, `scada_layout` y último estado de bombas en `RealtimeStateStore`.  
   - Inicia monitores de alarmas y watchdog SCADA.  
   - **Resultado**: La laguna está lista para recibir datos del collector y servir al frontend.

#### **Fase 4: Verificación End-to-End**

7. **Enviar Datos desde el Collector**  
   El collector envía payloads con el `lagoon_id` nuevo:  
   ```json
   {
     "lagoon_id": "costa_del_lago",
     "timestamp": "2026-04-09T18:20:00Z",
     "tags": {
       "PT117_R_SCADA": 2.31,
       "P006_STS_SCADA": 1
     }
   }
   ```
   - Endpoint: `POST /ingest/scada` con header `x-api-key`.  
   - **Flujo**: Se persiste en `scada_event`/`scada_minute`, evalúa alarmas, actualiza estado realtime y emite WebSocket.

8. **Verificar en el Frontend**  
   - Llama a `GET /api/crystal/lagoons` para listar lagunas.  
   - Obtiene mapping: `GET /lagoons/{lagoon_id}/mapping`.  
   - Conecta WebSocket: `GET /ws/scada/{lagoon_id}` para datos realtime.  
   - Renderiza SVG con overlays basados en layout + mapping + realtime.

9. **Configurar Thresholds de Alarmas (Opcional pero Recomendado)**  
   Define umbrales en `alarm_thresholds` para tags PT/FIT:  
   - Campos: `lagoon_id`, `tag_id`, `side` (`high`/`low`), `value`, etc.  
   - Usa el servicio `thresholds/service.py` para upsert.

Este proceso asegura que la nueva laguna esté completamente integrada en el flujo end-to-end: collector → backend → frontend. Si encuentras errores, revisa logs en `app/core/logging.py` o endpoints de health. Para automatizar, considera scripts SQL o APIs administrativas.
