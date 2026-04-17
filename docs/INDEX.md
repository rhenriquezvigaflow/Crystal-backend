# Documentacion Crystal Lagoons Backend

Indice curado de la documentacion vigente.

## Punto de entrada recomendado

1. `../README.md`
2. `ALARMAS_ACTUALES_Y_LOGICA.md`
3. `EMAIL_NOTIFICATIONS.md`
4. `README_ALARM_THRESHOLDS_API.md`

## Fuente de verdad por tema

### Backend operativo

- `../README.md`
  - setup rapido
  - rutas clave
  - diferencia entre rutas directas y rutas proxied por `/api`

### Alarmas

- `ALARMAS_ACTUALES_Y_LOGICA.md`
  - tipos soportados
  - criterios de apertura/cierre
  - precedencia de reglas de notificacion
  - limites actuales

### Email y notificaciones

- `EMAIL_NOTIFICATIONS.md`
  - flujo post-commit
  - payload SMTP
  - endpoint manual `/email/test-alert`
  - diferencias entre correo automatico y manual

### Umbrales PT/FIT

- `README_ALARM_THRESHOLDS_API.md`
  - contrato del endpoint
  - request/response
  - semantica de tags configurados vs candidatos

## Documentos de contexto adicional

Estos documentos siguen siendo utiles para onboarding o contexto historico, pero no reemplazan la fuente de verdad anterior:

- `ARQUITECTURA_Y_FLUJO.md`
- `ARQUITECTURA_END_TO_END_COLLECTOR_BACKEND.md`
- `FLUJO_INSERCION.md`
- `GUIA_TECNICA_DESARROLLO.md`
- `ONBOARDING.md`
- `DIAGRAMAS_FLUJOS.md`
- `ONE_PAGE_SUMMARY.md`
- `CHANGELOG.md`

## Criterio actual de mantenimiento

- si una ruta, payload o variable de entorno cambia, se actualiza primero `README.md`
- si el cambio toca alarmas o notificaciones, se actualiza ademas el documento tematico correspondiente
- se evita repetir tablas inventariadas desde BD dentro de documentos estaticos; para eso se prefieren queries o referencias al codigo
