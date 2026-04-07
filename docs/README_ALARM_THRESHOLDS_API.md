# API Alarmas de Umbral PT/FIT

## Rutas finales disponibles

Rutas base:

- `GET /alarms/{lagoon_id}/thresholds/pt-fit/view`
- `PUT /alarms/{lagoon_id}/thresholds/pt-fit`

Aliases de compatibilidad:

- `GET /crystal/alarms/{lagoon_id}/thresholds/pt-fit/view`
- `PUT /crystal/alarms/{lagoon_id}/thresholds/pt-fit`
- `GET /small/alarms/{lagoon_id}/thresholds/pt-fit/view`
- `PUT /small/alarms/{lagoon_id}/thresholds/pt-fit`
- `GET /api/alarms/{lagoon_id}/thresholds/pt-fit/view`
- `PUT /api/alarms/{lagoon_id}/thresholds/pt-fit`
- `GET /api/crystal/alarms/{lagoon_id}/thresholds/pt-fit/view`
- `PUT /api/crystal/alarms/{lagoon_id}/thresholds/pt-fit`
- `GET /api/small/alarms/{lagoon_id}/thresholds/pt-fit/view`
- `PUT /api/small/alarms/{lagoon_id}/thresholds/pt-fit`

Nota:

- El backend soporta rutas con y sin prefijo `/api`.
- Si el proxy reescribe `/api`, igual funciona.
- Si no reescribe `/api`, tambien funciona por alias nativo.

## Ejemplos curl

Definir:

```bash
BASE_URL="https://localhost"
TOKEN="<JWT_BEARER_TOKEN>"
LAGOON_ID="costa_del_lago"
```

### 1) View (consolidada, recomendada para frontend)

```bash
curl -k -X GET "$BASE_URL/alarms/$LAGOON_ID/thresholds/pt-fit/view" \
  -H "Authorization: Bearer $TOKEN"
```

Respuesta esperada (resumen):

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

### 2) Upsert

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

## Validaciones funcionales

- `tag_id` debe iniciar con `PT` o `FIT`.
- Debe venir `min_value` o `max_value`.
- Si vienen ambos: `min_value < max_value`.
- `severity` en `info|warning|critical`.
- `items` no puede estar vacio.

## Rendimiento (benchmark simple)

Medir latencia de lectura del endpoint consolidado (`/view`).

Script sugerido:

```bash
python scripts/bench_alarm_thresholds_view.py
```
