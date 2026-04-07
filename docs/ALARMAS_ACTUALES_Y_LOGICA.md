# Alarmas SCADA: estado actual, reglas y logica

## 1) Estado actual (backend + BD)

Fecha de corte: `2026-04-06` (consulta directa a BD en este entorno).

Alarmas habilitadas en `alarm_definition`:

- Total: `65`
- `state`: `33` (todas `critical`)
- `comm_loss`: `32` (`14 critical` y `18 warning`)
- `threshold`: `0` (soporte implementado, pero sin definiciones activas hoy)

Distribucion relevante:

- `state` bombas: `18`
- `state` valvulas: `15`
- `comm_loss` laguna (sin tag): `14` (una por laguna)
- `comm_loss` bombas: `18`

## 2) Tablas usadas por el sistema de alarmas

- `alarm_definition`: catalogo de definiciones (tipo, severidad, condicion JSON, etc.).
  - Nota PT/FIT: `deadband` se mantiene en BD pero para umbrales se fija internamente en `0.0`.
- `alarm_event`: ciclo de vida OPEN/CLOSED de cada alarma.
- `alarm_notification_rule`: reglas de enrutamiento de notificaciones.

Tablas SCADA que alimentan la logica:

- `scada_event`: usado para transiciones de estado (`previous_state -> state`).
- `scada_minute`: usado para descubrir tags PT/FIT en la vista consolidada de umbrales.

## 3) Tipos de alarma y reglas vigentes hoy

## 3.1) Alarmas de estado (`alarm_type = state`)

Regla vigente para bombas y valvulas:

- Condicion por transicion:
  - `condition = {"from_states":[1,2], "to_state":3}`
- Se abre cuando la ultima transicion del tag es `1->3` o `2->3`.

Mapa de estados SCADA usado:

- `0 = Detenida`
- `1 = Funcionando`
- `2 = Moviendose`
- `3 = Falla`

Notas:

- Esta regla reemplaza la logica anterior de "estado == 3" fijo.
- La evaluacion se apoya en `scada_event` para leer `previous_state` y `state`.

## 3.2) Alarmas de perdida de comunicacion (`alarm_type = comm_loss`)

Reglas vigentes:

- Bomba por tag (`warning`):
  - `condition = {"timeout_sec": 180}`
  - Si la edad desde `last_seen_ts` supera 180s, abre alarma.
- Laguna completa (`critical`, `tag_id = NULL`):
  - `condition = {"timeout_sec": 600}`
  - Si no entra senal a la laguna por mas de 10 min, abre alarma.

Implementacion:

- En `/ingest/scada`, cada payload actualiza observacion (`last_seen_ts`) para la laguna.
- En segundo plano, `AlarmLagoonSignalMonitor` evalua por reloj (intervalo configurable, default 30s).

## 3.3) Alarmas de umbral (`alarm_type = threshold`)

Estado actual:

- Motor implementado.
- API implementada para PT/FIT sobre contrato consolidado.
- Definiciones activas hoy en BD: `0`.

Contrato API vigente:

- Lectura:
  - `GET /alarms/{lagoon_id}/thresholds/pt-fit/view`
  - respuesta por tag con: `tag_id`, `tag_name`, `source`, `min_value`, `max_value`, `severity`, `enabled`
- Escritura:
  - `PUT /alarms/{lagoon_id}/thresholds/pt-fit`
  - payload por item: `tag_id`, `min_value`, `max_value`, `severity`, `enabled`

Semantica de `source`:

- `configured`: existe al menos una definicion threshold para el tag.
- `candidate`: tag descubierto en telemetria sin configuracion de umbral.

Formato de condicion soportado:

- Operador simple:
  - `{"op": ">", "value": 12.3}` (tambien `>=`, `<`, `<=`, `==`, `!=`)
- Rango:
  - `{"low": 2.0, "high": 8.0}`

Deadband:

- No es configurable desde API PT/FIT.
- Para umbrales PT/FIT se normaliza internamente a `0.0`.

## 4) Reglas de notificacion activas hoy (`alarm_notification_rule`)

Hay `4` reglas globales habilitadas:

1. `state + critical + tag_pattern='P%_ST%_SCADA'` -> `email` a `scada-alertas@tu-dominio.com`
2. `state + critical + tag_pattern='VE%_ST'` -> `email` a `scada-alertas@tu-dominio.com`
3. `comm_loss + warning + tag_pattern='P%_ST%_SCADA'` -> `email` a `scada-alertas@tu-dominio.com`
4. `comm_loss + critical + tag_pattern NULL` -> `email` a `scada-alertas@tu-dominio.com`

Importante:

- El canal `email` actual es mock (se registra en log, no envia SMTP real).
- Hay deduplicacion por `(channel, target)` para evitar duplicados de destino.

## 5) Logica operacional (motor de alarmas)

Flujo por ingest:

1. `ingest()` persiste datos SCADA.
2. `evaluate_alarms()` evalua definiciones relevantes de la laguna.
3. Si corresponde, abre/cierra en `alarm_event`.
4. Se hace `commit`.
5. `dispatch_notifications()` procesa jobs (mock por log).

Flujo por reloj (sin senal de laguna):

1. `AlarmLagoonSignalMonitor` corre cada N segundos.
2. Ejecuta `evaluate_lagoon_signal_alarms()`.
3. Abre/cierra `comm_loss` de laguna (`tag_id = NULL`) segun timeout.
4. Registra transiciones y notificaciones.

## 6) Ciclo de vida OPEN/CLOSED e idempotencia

Para abrir/cerrar:

- Lock pesimista por definicion (`FOR UPDATE`).
- Re-chequeo de evento activo antes de abrir.
- Indice unico parcial evita mas de un OPEN por definicion:
  - `uq_alarm_event_open_per_definition` (`status='OPEN'`).

## 7) Logging de alarmas

Loggers de alarmas:

- `alarms.service`
- `alarms.notifier`
- `alarms.silence_monitor`

Persistencia en archivo:

- Todo logger que empieza por `alarms.` tambien se escribe en:
  - `logs/alarmas.txt`
- Rotacion configurable por variables de entorno:
  - `ALARM_LOG_TO_FILE`
  - `ALARM_LOG_FILE_PATH`
  - `ALARM_LOG_MAX_BYTES`
  - `ALARM_LOG_BACKUP_COUNT`

## 8) Alcance y limites actuales

Cubre actualmente:

- Falla por transicion a estado `3` en bombas/valvulas.
- Perdida de comunicacion por tag de bomba.
- Laguna sin senal por reloj (10 min).
- Umbrales PT/FIT (infra y API listas para crear definiciones).

No aplicado hoy:

- No hay definiciones `threshold` cargadas actualmente en BD.
- Las notificaciones se emiten una sola vez por evento de alarma (solo en `OPEN`).
