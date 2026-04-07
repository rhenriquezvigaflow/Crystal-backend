# Prompt Frontend (Estado Actual PT/FIT)

## Rol
Eres un Senior Frontend Engineer (`React + TypeScript + Vite`) y debes implementar/modificar el modulo de configuracion de alarmas de umbral PT/FIT segun contrato backend vigente.

No priorices diseno visual.  
Prioriza flujo funcional, estado, validaciones, UX minima y conexion API real.

## Objetivo funcional

Implementar gestion de umbrales PT/FIT por laguna con este flujo:

1. Recibir `lagoon_id`.
2. Cargar listado consolidado por tag desde un endpoint unico.
3. Permitir edicion inline por fila (`min`, `max`, `severity`, `enabled`).
4. Guardar por fila con `PUT`.
5. Refrescar desde backend para mantener consistencia real.

## API backend disponible (contrato vigente)

### 1) Lectura consolidada (recomendada)
`GET /alarms/{lagoon_id}/thresholds/pt-fit/view`

Respuesta:
```json
{
  "lagoon_id": "costa_del_lago",
  "rows": [
    {
      "tag_id": "PT117_R_SCADA",
      "tag_name": "PT 117 Retorno",
      "source": "configured",
      "min_value": 1.2,
      "max_value": 8.5,
      "severity": "critical",
      "enabled": true
    }
  ]
}
```

### 2) Crear/actualizar umbrales
`PUT /alarms/{lagoon_id}/thresholds/pt-fit`

Body:
```json
{
  "items": [
    {
      "tag_id": "PT117_R_SCADA",
      "min_value": 1.2,
      "max_value": 8.5,
      "severity": "critical",
      "enabled": true
    }
  ]
}
```

Respuesta:
```json
{
  "ok": true,
  "lagoon_id": "costa_del_lago",
  "created": ["threshold_pt117_r_scada_min"],
  "updated": ["threshold_pt117_r_scada_max"]
}
```

Notas de contrato:

- `source` solo puede ser `configured` o `candidate`.
- `deadband` ya no forma parte del contrato frontend.
- `severity` es unico (no existe `severity_min` ni `severity_max`).
- Endpoints legacy `candidates` y `thresholds` separados ya no se usan.

## Contratos TypeScript requeridos

Define tipos para:

- `ThresholdViewRow`
- `ThresholdViewResponse`
- `ThresholdConfigItem`
- `ThresholdConfigRequest`
- `ThresholdConfigResponse`
- `AlarmThresholdRow` (modelo UI interno)

`AlarmThresholdRow` debe contener al menos:

- `tag_id`
- `tag_name`
- `source` (`configured` | `candidate`)
- `min_value | null`
- `max_value | null`
- `severity`
- `enabled`
- `dirty`

## Reglas funcionales y validaciones

- `tag_id` debe iniciar con `PT` o `FIT`.
- Debe existir al menos uno: `min_value` o `max_value`.
- Si ambos existen: `min_value < max_value`.
- `severity` en `info|warning|critical`.
- No enviar `PUT` con `items` vacio.

## UX requerida (estado actual)

- Popup con foco en panel/listado izquierdo (edicion inline por fila).
- Cada fila debe mostrar:
  - tag (`tag_id` y opcional `tag_name`)
  - estado textual: `Configurada` o `Sin Configurar`
  - input `Min`
  - input `Max`
  - selector `Severity`
  - switch `ON/OFF` (campo `enabled`)
  - boton `Guardar` por fila
- No mostrar boton global `Guardar pendientes`.
- Mensaje de exito al guardar: `Alarma guardada`.
- Si la laguna esta desconectada (`plc_status = offline`), valores de tarjetas deben mostrar `--.--`.

## Integracion API (implementacion)

Crear/usar:

- `services/alarm-thresholds.api.ts`
  - `getThresholdsView(lagoonId: string)`
  - `upsertThresholds(lagoonId: string, payload: ThresholdConfigRequest)`

Requisitos:

- Usar cliente HTTP central del proyecto.
- Inyectar `Authorization` (`Bearer`) segun arquitectura actual.
- Mantener parser comun de errores HTTP.

## Hook funcional recomendado

`hooks/useAlarmThresholds.ts` con:

- Estado:
  - `rows`
  - `loading`
  - `saving`
  - `error`
- Acciones:
  - `load(lagoonId)`
  - `updateRow(tagId, patch)`
  - `resetRow(tagId)`
  - `saveSelected(tagId)`

Comportamiento:

- `saveSelected` envia un item.
- Tras guardar, volver a `load(lagoonId)` para sincronizar estado real desde backend.

## Manejo de errores (obligatorio)

- `401/403`: error de autenticacion/permisos.
- `422`: error funcional de validacion (mostrar mensaje backend).
- `5xx` o red: error generico con opcion de reintento.

No ocultar errores; mantenerlos disponibles para logs/telemetria.

## Criterios de aceptacion tecnicos

1. La UI carga tags PT/FIT desde `GET /view`.
2. Se puede crear/editar por fila y guardar con `PUT`.
3. Estados visibles por tag: `Configurada` / `Sin Configurar`.
4. ON/OFF persiste correctamente en backend.
5. Validaciones previas a `PUT` alineadas con backend.
6. Mensaje de exito queda unificado en `Alarma guardada`.

