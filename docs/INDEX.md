# Documentacion Crystal Lagoons Backend

Indice curado de la documentacion vigente.

## Punto de Entrada Recomendado

1. `../README.md`
2. `ONE_PAGE_SUMMARY.md`
3. `ARQUITECTURA_Y_FLUJO.md`
4. `FLUJO_INSERCION.md`
5. `ALARMAS_ACTUALES_Y_LOGICA.md`
6. `EMAIL_NOTIFICATIONS.md`
7. `README_ALARM_THRESHOLDS_API.md`

## Fuente de Verdad por Tema

### Backend Operativo

- `../README.md`
  - setup rapido
  - endpoints activos
  - diferencia entre rutas directas y rutas proxied por `/api`

### Arquitectura

- `ONE_PAGE_SUMMARY.md`
  - mapa de 1 pagina
  - componentes principales
  - seguridad y BD clave
- `ARQUITECTURA_Y_FLUJO.md`
  - ciclo de vida
  - ingest
  - WebSocket
  - historico

### Alta de Lagunas e Ingest

- `FLUJO_INSERCION.md`
  - payload de ingest
  - metadata minima en BD
  - integracion con collector
  - relacion con escenas locales del frontend

### Alarmas

- `ALARMAS_ACTUALES_Y_LOGICA.md`
  - tipos soportados
  - criterios de apertura/cierre
  - precedencia de reglas de notificacion
  - limites actuales

### Email y Notificaciones

- `EMAIL_NOTIFICATIONS.md`
  - flujo post-commit
  - payload SMTP
  - endpoint manual `/email/test-alert`
  - diferencias entre correo automatico y manual

### Umbrales PT/FIT

- `README_ALARM_THRESHOLDS_API.md`
  - contrato del endpoint
  - request/response
  - validaciones

## Documentos de Contexto Adicional

- `ARQUITECTURA_END_TO_END_COLLECTOR_BACKEND.md`
- `GUIA_TECNICA_DESARROLLO.md`
- `ONBOARDING.md`
- `DIAGRAMAS_FLUJOS.md`
- `CHANGELOG.md`

## Criterio Actual de Mantenimiento

- Si cambia una ruta activa, se actualiza `../README.md` y `ARQUITECTURA_Y_FLUJO.md`.
- Si cambia el contrato consumido por frontend, se actualiza tambien `crystal-frontend/docs/API_CONTRACTS.md`.
- Si el cambio toca alarmas o notificaciones, se actualiza el documento tematico correspondiente.
- Los layouts visuales viven hoy en frontend como JSON locales; no documentar endpoints de layout backend si no estan registrados en `app/main.py`.
