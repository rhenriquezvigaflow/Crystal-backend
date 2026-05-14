# One-Page Summary - Crystal Lagoons Backend

**Version doc:** 2.0.0  
**Actualizado:** 2026-04-27

## Arquitectura en 30 Segundos

```text
SCADA Collector -- POST /ingest/scada + X-Api-Key --> FastAPI
                                                        |
                                                        +--> IngestService -> scada_event / scada_minute
                                                        +--> Alarm engine -> alarm_event / notifications
                                                        +--> RealtimeStateStore -> WebSocket tick
                                                        +--> PostgreSQL
                                                        +--> REST /scada/*, /lagoons, /alarms/*
```

El backend expone:

- Login JWT (`POST /auth/login`).
- Catalogo RBAC de lagunas (`GET /lagoons`).
- Lecturas SCADA (`/scada/{lagoon_id}/*`).
- Alarmas PT/FIT (`/alarms/{lagoon_id}/thresholds/pt-fit`).
- WebSocket autenticado (`/ws/scada/{lagoon_id}`).
- Endpoints Small operativos bajo `/api/small/*`.

El layout visual de la UI vive en el frontend: `crystal-frontend/src/assets/positions/*.json`.

## Flujo Principal Ingest

1. Collector envia `{lagoon_id, timestamp?, tags}` a `POST /ingest/scada`.
2. Backend valida `X-Api-Key`.
3. Si existe `sp_sync_collector_tags_and_alarms`, sincroniza tags/definiciones.
4. `IngestService` persiste eventos y buckets por minuto.
5. Se evaluan alarmas.
6. Se actualiza `RealtimeStateStore`.
7. Se emite `tick` por WebSocket a la laguna.
8. Respuesta HTTP: `{"ok": true}`.

## Seguridad

Ingest:

- Header obligatorio: `X-Api-Key: <COLLECTOR_API_KEY>`.

API usuario:

- `Authorization: Bearer <token>`.
- Roles: `AdminCrystal`, `VisualCrystal`, `AdminSmall`, `SuperAdmin`.
- Permisos por laguna desde `vw_user_lagoons`: `can_view`, `can_edit`, `can_control`.

WebSocket:

- Token por query o subprotocol.
- Requiere `can_view` o alcance por producto.

## Base de Datos Clave

- `lagoons`: catalogo, timezone, `product_type`, `enable`.
- `scada_event`: cambios de estado.
- `scada_minute`: valores historicos por minuto.
- `alarm_definition`, `alarm_event`, `alarm_notification_rule`.
- `users`, `roles`, `user_roles`.

Vistas/funciones esperadas por algunos flujos:

- `vw_user_lagoons`.
- `vw_scada_last_3_pump_actions`.
- `scada_minute_hourly`, `scada_minute_daily`, `scada_minute_weekly` si existen.
- `vw_alarm_thresholds_pt_fit_lagoon`.
- `sp_sync_collector_tags_and_alarms`, opcional.

## Setup Minimo

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8090
```

Variables minimas:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/crystal
COLLECTOR_API_KEY=replace-me
JWT_SECRET_KEY=replace-me
```

Mas detalle:

- [ARQUITECTURA_Y_FLUJO.md](./ARQUITECTURA_Y_FLUJO.md)
- [GUIA_TECNICA_DESARROLLO.md](./GUIA_TECNICA_DESARROLLO.md)
- [FLUJO_INSERCION.md](./FLUJO_INSERCION.md)
