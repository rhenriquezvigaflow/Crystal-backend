# Guia de Onboarding - Crystal Lagoons Backend

**Ultima actualizacion:** 2026-06-12  
**Tiempo estimado:** 2-4 horas

## Objetivo

Al finalizar deberias poder:

- levantar el backend local;
- autenticarte y consumir endpoints protegidos;
- enviar ingest con API key;
- leer historico y realtime;
- entender permisos por laguna;
- ubicar cambios de alarmas, email y WebSocket;
- coordinar alta de lagunas con collector y frontend.

## Ruta Sugerida

### Bloque 1 - Entender el Sistema

Lee en este orden:

1. [ONE_PAGE_SUMMARY.md](./ONE_PAGE_SUMMARY.md)
2. [ARQUITECTURA_Y_FLUJO.md](./ARQUITECTURA_Y_FLUJO.md)
3. [FLUJO_INSERCION.md](./FLUJO_INSERCION.md)

Checklist:

- sabes para que sirve `POST /ingest/scada`;
- entiendes diferencia entre realtime WS e historico REST;
- sabes que el layout visual vive en frontend;
- entiendes `lagoons`, `roles` y `vw_user_lagoons`.

### Bloque 2 - Setup Local

```powershell
cd crystal-backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8090
```

`.env` minimo:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/crystal
COLLECTOR_API_KEY=replace-me
JWT_SECRET_KEY=replace-me
```

Verificacion:

```powershell
curl http://localhost:8090/health
```

### Bloque 3 - Probar Flujo Extremo a Extremo

1. Login y guardar token.
2. Consultar lagunas:

```powershell
curl "http://localhost:8090/lagoons" `
  -H "Authorization: Bearer $TOKEN"
curl "http://localhost:8090/crystal/lagoons" `
  -H "Authorization: Bearer $TOKEN"
curl "http://localhost:8090/small/lagoons" `
  -H "Authorization: Bearer $TOKEN"
```

3. Probar historico:

```powershell
curl "http://localhost:8090/crystal/history?lagoon_id=costa_del_lago&start_date=2026-04-27T00:00:00Z&end_date=2026-04-27T23:59:59Z&resolution=hourly" `
  -H "Authorization: Bearer $TOKEN"
```

4. Conectar WebSocket:

```text
ws://localhost:8090/ws/crystal/costa_del_lago?token=<jwt>
```

5. Probar ingest con API key.

## Mapa Rapido de Archivos

Backend:

- `app/main.py`: bootstrap.
- `app/routers/ingest.py`: ingest.
- `app/routers/scada.py`: historico, realtime HTTP y KPIs.
- `app/routers/events.py`: eventos y reportes.
- `app/routers/websocket.py`: realtime WS.
- `app/auth/services/lagoon_service.py`: permisos por laguna.
- `app/alarms/thresholds/service.py`: umbrales PT/FIT.
- `app/services/email_service.py`: email.

Frontend relacionado:

- `crystal-frontend/src/assets/positions/*.json`: escenas visuales.
- `crystal-frontend/src/hooks/useScadaLayoutScene.ts`.
- `crystal-frontend/src/scada/lagoonSceneBundle.ts`.
- `crystal-frontend/src/scada/svgRegistry.ts`.

## Primer Cambio Seguro

Para un primer cambio de backend:

1. agrega o ajusta un test enfocado;
2. modifica solo el router/servicio involucrado;
3. corre `python -m pytest -q`;
4. si cambia contrato frontend, actualiza tambien `crystal-frontend/docs/API_CONTRACTS.md`.
