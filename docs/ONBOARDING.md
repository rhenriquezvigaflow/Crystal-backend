# Guia de Onboarding - Crystal Lagoons Backend

**Ultima actualizacion:** 2026-04-09
**Tiempo estimado:** 3-5 horas

---

## Objetivo

Al finalizar deberias poder:

- levantar el backend local,
- autenticarte y consumir endpoints protegidos,
- enviar ingest con API key,
- leer historico y realtime,
- entender el sistema de layouts SCADA reutilizables,
- ubicar donde hacer cambios de alarmas, mappings y estados SCADA.

---

## Ruta sugerida

### Bloque 1 - Entender el sistema

Lee en este orden:

1. [ONE_PAGE_SUMMARY.md](./ONE_PAGE_SUMMARY.md)
2. [ARQUITECTURA_Y_FLUJO.md](./ARQUITECTURA_Y_FLUJO.md)
3. [FLUJO_INSERCION.md](./FLUJO_INSERCION.md)

Checklist:

- sabes para que sirve `POST /ingest/scada`.
- entiendes diferencia entre realtime WS e historico REST.
- entiendes que `layouts` define estructura y `lagoon_layout_mapping` define tags/labels por laguna.
- sabes que `collector_tags` decide que tarjetas se muestran.

---

### Bloque 2 - Setup local

```bash
cd crystal-backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

`.env` minimo:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/crystal
COLLECTOR_API_KEY=replace-me
JWT_SECRET_KEY=replace-me
```

Verificacion:

```bash
curl http://localhost:8000/health
```

---

### Bloque 3 - Probar flujo extremo a extremo

1. Login y guardar token.
2. Consultar lagunas:

```bash
curl "http://localhost:8000/api/crystal/lagoons" \
  -H "Authorization: Bearer $TOKEN"
```

3. Consultar layout/mapping:

```bash
curl "http://localhost:8000/lagoons/costa_del_lago/mapping" \
  -H "Authorization: Bearer $TOKEN"

curl "http://localhost:8000/layouts/layout1" \
  -H "Authorization: Bearer $TOKEN"
```

4. Probar historico:

```bash
curl "http://localhost:8000/api/crystal/history?lagoon_id=costa_del_lago&start_date=2026-04-09T00:00:00Z&end_date=2026-04-09T23:59:59Z&resolution=hourly" \
  -H "Authorization: Bearer $TOKEN"
```

5. Conectar WebSocket:

```text
ws://localhost:8000/ws/scada/costa_del_lago?token=<jwt>
```

---

## Mapa rapido de archivos

Backend:

- `app/main.py`: bootstrap.
- `app/routers/ingest.py`: ingest.
- `app/layout_config/service.py`: cache y validacion layout/mapping.
- `app/routers/scada_layouts.py`: endpoints generales de layout.
- `app/routers/crystal/lagoons.py`: layout-config Crystal.
- `app/routers/small/lagoons.py`: layout-config Small.
- `app/scada/history/repo.py`: historico.
- `app/alarms/thresholds/service.py`: umbrales PT/FIT.

Frontend relacionado:

- `src/hooks/useScadaLayoutScene.ts`.
- `src/scada/layoutSceneResolver.ts`.
- `src/containers/ScadaOverlay.tsx`.
- `src/containers/ScadaEquipmentStateOverlay.tsx`.
- `src/scada/equipment-state/layouts/*.equipment.json`.
- `src/scada/labels/layouts/*.base.json`.

---

## Siguiente paso recomendado

Para un primer cambio seguro:

1. agrega o ajusta un elemento en `layouts.json_definition` en BD,
2. valida que existe en `mapping_json`,
3. corre `python -m pytest -q`,
4. valida frontend con `npm run build`.
