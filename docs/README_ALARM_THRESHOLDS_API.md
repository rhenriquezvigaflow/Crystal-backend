# API Alarmas de Umbral PT/FIT

**Actualizado:** 2026-04-27

## Rutas Disponibles

Lectura:

- `GET /alarms/{lagoon_id}/thresholds/pt-fit/view`

Escritura:

- `PUT /alarms/{lagoon_id}/thresholds/pt-fit`

Detras de proxy, el frontend normalmente las consume como:

- `GET /api/alarms/{lagoon_id}/thresholds/pt-fit/view`
- `PUT /api/alarms/{lagoon_id}/thresholds/pt-fit`

No hay aliases activos `/crystal/alarms/*` ni `/small/alarms/*` registrados en `app/main.py`.

## Obtener Vista Consolidada

```powershell
curl -X GET "$BASE_URL/alarms/$LAGOON_ID/thresholds/pt-fit/view" `
  -H "Authorization: Bearer $TOKEN"
```

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

## Guardar Umbrales

```powershell
curl -X PUT "$BASE_URL/alarms/$LAGOON_ID/thresholds/pt-fit" `
  -H "Authorization: Bearer $TOKEN" `
  -H "Content-Type: application/json" `
  -d '{
    "items": [
      {
        "tag_id": "PT117_R_SCADA",
        "min_value": 1.2,
        "max_value": 8.5,
        "severity": "critical",
        "enabled": true
      }
    ]
  }'
```

Respuesta:

```json
{
  "ok": true,
  "lagoon_id": "costa_del_lago",
  "created": ["threshold_PT117_R_SCADA_min"],
  "updated": ["threshold_PT117_R_SCADA_max"]
}
```

## Validaciones Funcionales

- `tag_id` debe iniciar con `PT` o `FIT`.
- Debe venir `min_value` o `max_value`.
- Si vienen ambos, `min_value < max_value`.
- `severity` en `info|warning|critical`.
- `items` no puede estar vacio.
- El usuario debe tener permiso `can_view` para lectura y `can_edit` para escritura.

## Integracion Frontend

Archivos:

- `src/components/AlarmManagerModal.tsx`
- `src/hooks/useAlarmThresholds.ts`
- `src/services/alarm-thresholds.api.ts`
- `src/types/alarm-thresholds.ts`

La UI mezcla:

- filas `configured` desde backend;
- candidatos PT/FIT detectados por realtime;
- permisos `can_edit` para habilitar guardado.
