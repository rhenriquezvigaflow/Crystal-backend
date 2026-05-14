# Notificaciones Email

**Actualizado:** 2026-04-27

Documento de referencia para el flujo SMTP actual del backend.

## Arquitectura actual

La notificacion no esta acoplada al commit principal.

Flujo:

1. el motor de alarmas genera `NotificationJob`
2. la transaccion de DB hace `commit`
3. `dispatch_notifications()` entrega los jobs al `NotificationOrchestrator`
4. el orquestador despacha cada job en `ThreadPoolExecutor`
5. `EmailService` renderiza `app/templates/email/alarm_notification.html`
6. `fastapi-mail` envia el correo por SMTP

Esto aplica tanto al flujo de ingest como al monitor de laguna sin senal.

## Componentes

- `app/alarms/notifier.py`: punto de entrada para despacho
- `app/integration/notifications.py`: `NotificationOrchestrator`
- `app/services/email_service.py`: render y envio SMTP
- `app/schemas/notifications.py`: payloads tipados y request manual
- `app/templates/email/alarm_notification.html`: plantilla HTML

## Canales

- `email`: real
- `webhook`: simulado por log

Si llega un canal no soportado:

- se registra `[NOTIFY SKIP]`
- no se cae el flujo principal

## Reglas de destinatarios

Normalizacion:

- acepta string con `,` o `;`
- acepta lista
- trim de espacios
- deduplicacion case-insensitive

Validacion:

- `AlarmNotificationPayload.recipients` usa `EmailStr`
- si una regla de BD produce correos invalidos, la regla se descarta con log

## Email automatico de alarmas

El email automatico nace en `app/alarms/service.py`.

Para esos correos:

- `critical` o `high` -> `level=lvl2`
- cualquier otro caso -> `level=lvl1`

El asunto final sale de `AlarmNotificationPayload.subject`:

```text
[LVL2] <plant_name o lagoon_id> - <title>
```

Ejemplos de `title` automatico:

- `State alarm for P005_STS_SCADA`
- `Threshold alarm for PT117_R_SCADA`
- `Communication loss alarm for lagoon costa_del_lago`

## Endpoint manual de prueba

Ruta:

- `POST /email/test-alert`

Autorizacion:

- requiere roles de lectura (`ALL_READ_ROLES`)

Precondicion:

- si SMTP no esta configurado, responde `503`

Semantica:

- crea un `AlarmNotificationPayload` manual
- genera un `event_id` nuevo
- lo encola en `BackgroundTasks`

Payload de ejemplo:

```json
{
  "lagoon_id": "costa_del_lago",
  "plant_name": "Costa del Lago",
  "title": "Prueba manual SCADA",
  "description": "Correo de validacion SMTP",
  "priority": "warning",
  "recipients": ["equipo@dominio.com"]
}
```

Respuesta:

```json
{
  "ok": true,
  "queued": true,
  "lagoon_id": "costa_del_lago",
  "recipients": ["equipo@dominio.com"]
}
```

Importante:

- si el request manual no trae `level`, el asunto usa `priority.upper()`
- por eso un correo manual puede quedar como `[WARNING] ...`
- en cambio los correos automaticos del motor normalmente salen como `[LVL1]` o `[LVL2]`

## Variables de entorno

- `MAIL_USERNAME`
- `MAIL_PASSWORD`
- `MAIL_FROM`
- `MAIL_PORT`
- `MAIL_SERVER`
- `MAIL_STARTTLS`
- `MAIL_SSL_TLS`
- `MAIL_FROM_NAME`
- `MAIL_TIMEOUT_SEC`
- `MAIL_DISPATCH_MAX_WORKERS`

`EmailService.is_configured` exige:

- username
- password
- from
- server
- port valido

## Comportamiento ante errores

Si falla SMTP:

- `EmailService` registra `[EMAIL SMTP ERROR]`
- el orquestador captura la excepcion y registra `[NOTIFY ERROR]`
- la transaccion de ingest o del monitor ya quedo comprometida, no se revierte

Si SMTP funciona:

- `EmailService` registra `[EMAIL SMTP OK]`
- el orquestador registra `[EMAIL SENT]`

## Limites actuales

- no hay retries de envio
- no hay outbox table ni cola durable
- no hay batching ni digest
- no hay webhook real
- `asyncio.run()` se usa por job en el camino sync del orquestador
