# Alarmas SCADA: estado actual y logica

**Actualizado:** 2026-04-27

Documento alineado al codigo actual del backend. Este archivo describe la logica soportada por el motor; no fija inventarios numericos de BD para evitar que la documentacion quede obsoleta.

## Flujo real del motor

### Durante ingest

1. `POST /ingest/scada` entra por `app/routers/ingest.py`.
2. `ingest()` persiste `scada_minute` y detecta `scada_event`.
3. `evaluate_alarms()` evalua las definiciones relevantes para la laguna.
4. Si corresponde, abre o cierra `alarm_event`.
5. Se hace `commit`.
6. Recien despues del commit se llama `dispatch_notifications()`.

### Por reloj de servidor

1. `AlarmLagoonSignalMonitor` corre en background.
2. `evaluate_lagoon_signal_alarms()` revisa definiciones `comm_loss` a nivel laguna.
3. Si hay transiciones, persiste `alarm_event`.
4. Hace `commit`.
5. Despacha notificaciones post-commit.

## Tipos de alarma soportados

## 1) `state`

El motor soporta varias formas de condicion:

- transicion:
  - `{"from_states":[1,2], "to_state":3}`
- igualdad:
  - `{"equals":3}`
- inclusion:
  - `{"states":[2,3]}`
- exclusion:
  - `{"not_in":[0,1]}`

Implementacion:

- las transiciones usan `scada_event` como fuente de verdad para obtener `previous_state` y `state`
- las demas variantes evaluan el valor actual del tag en el payload

Comportamiento:

- si la condicion queda activa y no existe evento abierto, se crea `OPEN`
- si deja de cumplirse y existe un evento abierto, se crea `CLOSE`

## 2) `comm_loss`

### Por tag

- se evalua dentro de `evaluate_alarms()`
- si el tag viene presente y con valor, se considera comunicacion restaurada
- si el tag deja de llegar, se compara la edad contra `timeout_sec`

Condicion soportada:

- `{"timeout_sec": 180}`

### Por laguna completa

- se evalua solo en el monitor de fondo
- aplica a definiciones con `tag_id = NULL`
- usa el reloj del servidor y `last_seen_ts`

Condicion soportada:

- `{"timeout_sec": 3600}`

## 3) `threshold`

Soporta dos formatos:

- operador:
  - `{"op": ">", "value": 12.3}`
  - operadores validos: `>`, `>=`, `<`, `<=`, `==`, `!=`
- rango:
  - `{"low": 2.0, "high": 8.0}`

Deadband:

- si la condicion trae `deadband`, se usa ese valor
- si no, cae a `definition.deadband`
- cuando la alarma ya esta abierta, el deadband se aplica como histeresis para evitar flapping

Casos no evaluables:

- tag ausente
- valor no numerico
- threshold sin limites validos

## Seleccion de definiciones

`AlarmRepository.get_definitions()` trae:

- definiciones habilitadas de la laguna
- `state` y `threshold` solo si su `tag_id` viene en el payload
- `comm_loss` siempre, incluso si el payload llega vacio

## Ciclo de vida e idempotencia

El motor evita duplicados con varias capas:

- lock pesimista `FOR UPDATE` sobre la definicion
- re-chequeo del evento `OPEN` antes de crear uno nuevo
- cierre solo si existe un evento `OPEN`

Resultado:

- una definicion no deberia abrir mas de un evento simultaneo
- los cierres son idempotentes si el evento ya fue cerrado

## Reglas de notificacion

Las reglas salen de `alarm_notification_rule`.

Precedencia:

1. regla atada a `alarm_definition_id`
2. regla por `lagoon_id`
3. regla global

Filtros adicionales:

- `alarm_type`
- `severity`
- `tag_pattern`

Compatibilidad de `tag_pattern`:

- el backend acepta patrones historicos estilo SQL LIKE con `%`
- internamente se convierten a `fnmatch` (`%` -> `*`)

Deduplicacion:

- despues del match, se eliminan duplicados por `(channel, target)`

Importante:

- solo las transiciones `OPEN` generan jobs automaticos de notificacion
- las transiciones `CLOSE` se persisten y se loggean, pero no disparan notificaciones

## Canales soportados

- `email`: envio real via SMTP
- `webhook`: simulado por log, sin POST HTTP real

Detalle del flujo email en:

- `EMAIL_NOTIFICATIONS.md`

## Titulos y payloads de email automatico

Cuando la notificacion nace desde una alarma del motor:

- `critical` o `high` -> `LVL2`
- resto -> `LVL1`

Titulos:

- `threshold`: `Threshold alarm for <tag>`
- `state`: `State alarm for <tag>`
- `comm_loss` por tag: `Communication loss alarm for <tag>`
- `comm_loss` por laguna: `Communication loss alarm for lagoon <lagoon_id>`

## Logging relevante

Loggers:

- `alarms.service`
- `alarms.silence_monitor`
- `alarms.thresholds.service`
- `alarms.notification.orchestrator`
- `alarms.email.service`

Mensajes utiles:

- `[ALARM OPEN]`
- `[ALARM CLOSE]`
- `[NOTIFY SKIP]`
- `[NOTIFY RULE SKIP]`
- `[EMAIL SENT]`
- `[WEBHOOK SIMULATED]`

## Consultas utiles para validar estado real de BD

Definiciones habilitadas por tipo:

```sql
SELECT alarm_type, severity, count(*)
FROM alarm_definition
WHERE enabled = true
GROUP BY alarm_type, severity
ORDER BY alarm_type, severity;
```

Eventos abiertos:

```sql
SELECT lagoon_id, tag_id, alarm_type, severity, opened_at
FROM alarm_event
WHERE status = 'OPEN'
ORDER BY opened_at DESC;
```

Reglas de notificacion activas:

```sql
SELECT channel, target, lagoon_id, alarm_definition_id, alarm_type, severity, tag_pattern
FROM alarm_notification_rule
WHERE enabled = true
ORDER BY channel, target;
```

## Limites actuales

- no hay cooldown entre notificaciones del mismo evento
- no hay retries ni cola durable para email
- no hay agrupacion de emails
- `webhook` sigue siendo solo logging
- los inventarios exactos de definiciones dependen de la BD y deben consultarse con SQL, no con texto estatico
