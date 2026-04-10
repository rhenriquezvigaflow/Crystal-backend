# API Alarmas de Umbral PT/FIT

**Actualizado:** 2026-04-09

---

## Rutas disponibles

Rutas base:

- `GET /alarms/{lagoon_id}/thresholds/pt-fit/view`
- `PUT /alarms/{lagoon_id}/thresholds/pt-fit`

Aliases de compatibilidad:

- `GET|PUT /crystal/alarms/{lagoon_id}/thresholds/pt-fit[/view]`
- `GET|PUT /small/alarms/{lagoon_id}/thresholds/pt-fit[/view]`
- `GET|PUT /api/alarms/{lagoon_id}/thresholds/pt-fit[/view]`
- `GET|PUT /api/crystal/alarms/{lagoon_id}/thresholds/pt-fit[/view]`
- `GET|PUT /api/small/alarms/{lagoon_id}/thresholds/pt-fit[/view]`

Nota:

- El frontend usa prefijo cacheado por laguna y fallback entre rutas.
- La vista `/view` es el contrato recomendado para lectura.

---

## Obtener vista consolidada

```bash
curl -k -X GET "$BASE_URL/alarms/$LAGOON_ID/thresholds/pt-fit/view" \
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

---

## Guardar umbrales

```bash
curl -k -X PUT "$BASE_URL/alarms/$LAGOON_ID/thresholds/pt-fit" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
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

---

## Validaciones funcionales

- `tag_id` debe iniciar con `PT` o `FIT`.
- Debe venir `min_value` o `max_value`.
- Si vienen ambos, `min_value < max_value`.
- `severity` en `info|warning|critical`.
- `items` no puede estar vacio.

---

## Integracion frontend

Archivos:

- `src/components/AlarmManagerModal.tsx`
- `src/hooks/useAlarmThresholds.ts`
- `src/services/alarm-thresholds.api.ts`
- `src/types/alarm-thresholds.ts`

La UI mezcla:

- filas `configured` desde backend,
- candidatos PT/FIT detectados por realtime,
- permisos `can_edit` para habilitar guardado.
