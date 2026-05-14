# Flujo de Insercion y Publicacion SCADA

**Version doc:** 2.0.0  
**Actualizado:** 2026-04-27

## 1. Entrada de Datos

Endpoint:

- `POST /ingest/scada`

Requisitos:

- Header `X-Api-Key` valido.
- Body JSON con `lagoon_id`, `timestamp` opcional y `tags`.

Ejemplo:

```json
{
  "lagoon_id": "costa_del_lago",
  "timestamp": "2026-04-27T18:20:00Z",
  "tags": {
    "PT117_R_SCADA": 2.31,
    "P006_STS_SCADA": 1
  }
}
```

## 2. Secuencia Ingest

1. `ingest_scada` valida API key y payload.
2. Normaliza timestamp a UTC.
3. Ejecuta persistencia con timeout (`INGEST_REQUEST_TIMEOUT_SEC`).
4. Si existe `sp_sync_collector_tags_and_alarms`, sincroniza tags y definiciones.
5. `ingest_service.ingest(...)` detecta cambios de estado, cierra eventos abiertos, crea eventos nuevos y actualiza `scada_minute`.
6. Se evalua motor de alarmas.
7. Se hace `commit`.
8. Se despachan notificaciones post-commit cuando corresponde.
9. Se actualiza `RealtimeStateStore`.
10. Se emite `tick` via WebSocket.
11. Respuesta `200 {"ok": true}`.

## 3. Estado Realtime

`RealtimeStateStore` conserva por laguna:

- `tags` actuales;
- `last_ts`;
- `pump_last_on`;
- `start_ts`;
- `timezone`.

En cada payload WebSocket se agregan:

- `plc_status` (`online|offline`);
- `local_time` segun timezone de la laguna;
- `pump_last_on`.

## 4. Bootstrap al Iniciar

En `lifespan`:

1. Carga lagunas habilitadas desde `lagoons`.
2. Precarga timezone por laguna.
3. Detecta lagunas con eventos.
4. Precarga ultimo `pump_last_on` por bomba desde `scada_event`.
5. Inicia `ScadaStallWatchdog`.
6. Inicia `AlarmLagoonSignalMonitor`.

## 5. Lecturas REST Asociadas

SCADA:

- `GET /scada/{lagoon_id}/realtime`
- `GET /scada/{lagoon_id}/history`
- `GET /scada/{lagoon_id}/kpis`
- `GET /scada/{lagoon_id}/events`
- `GET /scada/{lagoon_id}/pump-events`
- `GET /scada/{lagoon_id}/pump-events/last-3`
- `GET /scada/{lagoon_id}/pump-events/report.xlsx`

Lagunas y permisos:

- `GET /lagoons`
- `PUT /lagoons/{id}`
- `POST /control/pump`

Alarmas PT/FIT:

- `GET /alarms/{lagoon_id}/thresholds/pt-fit/view`
- `PUT /alarms/{lagoon_id}/thresholds/pt-fit`

## 6. Flujo de Historico

Implementacion: `app/scada/history/repo.py`.

Reglas:

1. Resolucion valida: `hourly|daily|weekly`.
2. Si `end_date < start_date`, se invierte el rango.
3. Si existe vista continua (`scada_minute_<resolution>`), `source = "view"`.
4. Si no existe, fallback sobre `scada_minute`, `source = "table"`.
5. Respuesta: `series[{tag, points}]`.

## 7. Flujo Visual SCADA

El backend ya no es la fuente visual de layouts. La fuente actual esta en frontend:

- `crystal-frontend/src/assets/positions/*.json`
- `crystal-frontend/src/scada/svgRegistry.ts`

Flujo:

1. Backend entrega lagunas visibles por `GET /lagoons`.
2. Frontend carga `src/assets/positions/{lagoon_id}.json`.
3. Frontend abre `WS /ws/scada/{lagoon_id}`.
4. Frontend mezcla escena local + tags realtime.
5. Si no hay realtime en 7 segundos, muestra el plano con `--`.

## 8. Estados SVG de Bombas y Valvulas

Los valores discretos se interpretan asi:

- `0`: rojo.
- `1`: verde.
- `2`: azul.
- `3`: amarillo.
- sin dato: gris.

El backend solo entrega tags. La aplicacion de color se hace en frontend sobre `svg_target`.

## 9. Flujo de Umbrales PT/FIT

1. Frontend consulta `GET /alarms/{lagoon_id}/thresholds/pt-fit/view`.
2. Backend responde filas consolidadas por `tag_id`.
3. Frontend guarda con `PUT /alarms/{lagoon_id}/thresholds/pt-fit`.
4. Backend crea/actualiza codigos `threshold_<tag>_min` y `threshold_<tag>_max`.

Validaciones:

- `tag_id` inicia con `PT` o `FIT`.
- debe venir `min_value` o `max_value`.
- si ambos vienen, `min_value < max_value`.
- `severity` en `info|warning|critical`.

## 10. Alta de una Nueva Planta o Laguna

En codigo y base de datos el identificador canonico es `lagoon_id`.

### Checklist Previo

Definir:

- `lagoon_id` unico y estable, en minusculas y con `_`, por ejemplo `ary`;
- nombre visible;
- `product_type`: `crystal` o `small`;
- timezone IANA valida;
- IP y tipo PLC;
- inventario inicial de tags del collector;
- escena frontend en `src/assets/positions/<lagoon_id>.json`;
- usuarios o roles que deben ver/editar/controlar.

### Paso 1: Crear YAML del Collector

Ejemplo:

```yaml
lagoon_id: "ary"
source: rockwell
poll_seconds: 1
timezone: "Asia/Karachi"

backend:
  url: "http://127.0.0.1:8090/ingest/scada"

rockwell:
  ip: "192.168.18.10"
  slot: 0

tags:
  PT117_R: "PT117_R"
  FIT002_R: "FIT002_R"
  P005_ST: "P005_ST"
```

Si usas master config, agregar include en `collector_python/collectors.yml`.

### Paso 2: Crear Registro Base en `lagoons`

Ejemplo SQL:

```sql
INSERT INTO lagoons (
  id,
  name,
  plc_type,
  timezone,
  ip,
  enable,
  product_type
)
VALUES (
  'ary',
  'ARY',
  'Rockwell',
  'Asia/Karachi',
  '192.168.18.10',
  TRUE,
  'crystal'
);
```

Validacion:

```sql
SELECT id, name, product_type, timezone, enable
FROM lagoons
WHERE id = 'ary';
```

### Paso 3: Crear Escena Frontend

Crear:

- `crystal-frontend/src/assets/positions/ary.json`

Debe incluir al menos:

- `lagoon_id`
- `layout_id`
- `svg_component`
- `kpis`
- `pumps`
- `valves`
- `labels`
- `plc_status`

### Paso 4: Asignar Permisos

Validar `vw_user_lagoons`:

```sql
SELECT user_id, lagoon_id, can_view, can_edit, can_control
FROM vw_user_lagoons
WHERE lagoon_id = 'ary'
ORDER BY user_id;
```

### Paso 5: Reiniciar y Validar

Reiniciar backend si hubo alta o cambio de timezone.

Checklist:

1. `GET /lagoons` muestra la laguna.
2. `POST /ingest/scada` responde `{"ok": true}`.
3. `WS /ws/scada/{lagoon_id}` entrega `tags`.
4. El frontend tiene `src/assets/positions/{lagoon_id}.json`.
5. Los tags del JSON coinciden con los tags enviados por collector.

## 11. Errores Frecuentes

- La planta no aparece en frontend: revisar `lagoons.enable`, `product_type`, roles y `vw_user_lagoons`.
- El mapa no carga: falta JSON en `src/assets/positions`.
- Hay realtime pero tarjetas en `--`: tags del collector no coinciden con la escena.
- Colores no cambian: `svg_target` no existe en el SVG o el valor no esta en `0..3`.
- No aparece `local_time`: revisar `timezone` y reiniciar backend despues de alta.
