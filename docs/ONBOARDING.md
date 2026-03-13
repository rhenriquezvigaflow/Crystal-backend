# Guia de Onboarding - Crystal Lagoons Backend

**Ultima actualizacion:** 2026-03-13
**Tiempo estimado:** 3-5 horas

---

## Objetivo

Al finalizar deberias poder:

- levantar el backend local,
- autenticarte y consumir endpoints protegidos,
- enviar ingest con API key,
- leer datos SCADA y websocket,
- entender donde hacer cambios.

---

## Ruta sugerida

### Bloque 1 (45 min) - Entender el sistema

Lee en este orden:

1. [ONE_PAGE_SUMMARY.md](./ONE_PAGE_SUMMARY.md)
2. [ARQUITECTURA_Y_FLUJO.md](./ARQUITECTURA_Y_FLUJO.md)
3. [FLUJO_INSERCION.md](./FLUJO_INSERCION.md)

Checklist:

- sabes para que sirve `POST /ingest/scada`.
- entiendes diferencia entre `current`, `last-minute` e `history`.
- entiendes que WS requiere token + permiso por laguna.

---

### Bloque 2 (60 min) - Setup local

```bash
cd crystal-backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Crear `.env` minimo:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/crystal
COLLECTOR_API_KEY=replace-me
JWT_SECRET_KEY=replace-me
```

Inicializar RBAC:

```bash
psql "$DATABASE_URL" -f scripts/sql/create_rbac_tables.sql
python scripts/seed_roles.py
```

Opcional (vistas historicas):

```bash
psql "$DATABASE_URL" -f scripts/sql/create_scada_continuous_aggregates.sql
```

Levantar API:

```bash
python -m uvicorn app.main:app --reload
```

Verificacion:

```bash
curl http://localhost:8000/health
```

---

### Bloque 3 (45 min) - Probar flujo extremo a extremo

1) Login:

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"Secret123!"}'
```

2) Ingest:

```bash
curl -X POST http://localhost:8000/ingest/scada \
  -H "Content-Type: application/json" \
  -H "x-api-key: $COLLECTOR_API_KEY" \
  -d '{"lagoon_id":"laguna_1","tags":{"bomba_1":1,"temperatura":28.5}}'
```

3) Lectura protegida:

```bash
curl "http://localhost:8000/scada/laguna_1/current" \
  -H "Authorization: Bearer $TOKEN"
```

4) WebSocket:

- conectar a `ws://localhost:8000/ws/scada?lagoon_id=laguna_1&token=<jwt>`
- confirmar recepcion de `snapshot` y luego `tick`.

---

### Bloque 4 (45 min) - Primer cambio sugerido

Cambio pequeno recomendado:

- agregar test para endpoint protegido o para permiso RBAC.

Flujo:

```bash
git checkout -b feature/onboarding-primer-cambio
pytest tests/test_rbac_permissions.py -v
# editar
pytest tests/ -v
git add .
git commit -m "test: cubrir caso de permiso faltante"
git push origin feature/onboarding-primer-cambio
```

---

## Mapa rapido de archivos

- `app/main.py`: bootstrap, routers, CORS.
- `app/routers/ingest.py`: endpoint ingest + API key.
- `app/security/rbac.py`: roles, permisos y WS auth.
- `app/auth/auth.py`: login.
- `app/state/store.py`: payload realtime.
- `app/scada/history/repo.py`: resolucion y fallback historico.

---

## Preguntas frecuentes

### Que credenciales uso para login?

Depende de los usuarios existentes en tu BD (`users`).

### Por que recibo 403 con token valido?

Token valido no implica permiso por laguna; revisar `vw_user_lagoons`.

### Por que ingest devuelve 401?

Falta o no coincide `x-api-key`.

### Por que websocket cierra con 1008?

Token invalido/faltante o usuario sin `can_view` para la laguna.

---

## Siguiente paso recomendado

Despues de onboarding:

1. tomar un bug pequeno en auth o scada read,
2. agregar test de regresion,
3. actualizar `docs/CHANGELOG.md` si cambias contrato.
