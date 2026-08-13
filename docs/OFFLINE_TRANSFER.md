# Transferencia resumible del Collector Offline

## Resumen de la decision

Un atraso de 1 GB no debe enviarse como un JSON ni como una unica solicitud
HTTP. La solucion implementada genera muchos archivos deterministas `CSV.gz`,
los divide en partes reintentables y los importa en segundo plano. Cada
transferencia representa exactamente un chunk y conserva su identidad durante
todos los reintentos.

Limites usados por el generador del nodo:

- hasta 20.000 filas;
- hasta 25 MiB sin comprimir;
- partes de 1 MiB;
- `source=collector_offline` exacto y en minusculas.

El centro deja margen operativo y acepta hasta 32 MiB sin comprimir, 32 MiB
comprimidos y partes de hasta 2 MiB. Esos topes centrales no cambian el limite
de 25 MiB que debe aplicar el builder del nodo.

Por tanto, 1 GB se drena como una secuencia de chunks pequenos. Si se corta la
red, se reanuda desde la primera parte no confirmada; no se vuelve a enviar el
gigabyte completo.

## Arquitectura observada

```text
Collector online
    |
    | POST JSON /ingest/scada
    v
IIS HTTPS /api/* ---> Uvicorn/FastAPI :8090 (un proceso)
                          |
                          v
                  PostgreSQL + TimescaleDB
                  scada_minute / scada_event
                  CAGG hourly/daily/weekly
```

El camino online es adecuado para lotes pequenos y baja latencia. El mecanismo
anterior de backfill JSON hacia el mismo proceso no era apropiado para un atraso
grande: repetia parseo JSON, mantendria solicitudes largas, no tenia reanudacion
por byte y competia con el API de tiempo real.

Puntos operativos encontrados:

- IIS publica el backend bajo `/api`; las rutas FastAPI no llevan ese prefijo.
- El servicio Uvicorn actual escucha en `0.0.0.0:8090`. Debe limitarse a
  `127.0.0.1` o protegerse con firewall para que la autenticacion y los limites
  de IIS no puedan eludirse.
- El certificado HTTPS observado corresponde al nombre `crystalscada`; el
  nodo remoto debe resolver ese nombre y confiar explicitamente en el
  certificado. No se debe desactivar la validacion TLS.
- `scada_minute` es un hypertable grande con chunks comprimidos. La migracion
  agrega `source` sin actualizar masivamente el historico existente.

## Arquitectura propuesta e implementada

```text
Collector Offline
  PostgreSQL local / backlog
      |
      | chunk determinista <= 20k filas / 25 MiB sin comprimir
      v
  CSV UTF-8 -> gzip -> SHA-256 -> manifest
      |
      | POST manifest
      | PUT partes de 1 MiB (reintento idempotente)
      | POST complete
      v
IIS HTTPS /api/offline-transfer
      |
      v
FastAPI (registro, estado y spool durable)
      |
      +--> D:\CrystalBackfill
      |       Incoming / Ready / Imported / Failed
      |
      v
POST complete sincrono (un import global)
      |
      | gzip/CSV streaming -> COPY a tabla temporal
      | validacion -> merge idempotente -> COMMIT
      v
PostgreSQL + TimescaleDB
      |
      v
VERIFIED -> el Collector Offline puede borrar su chunk local
```

La base de datos es la autoridad final: `VERIFIED` solo se publica despues
de importar y confirmar `inserted_rows + duplicate_rows = row_count`. Locks
advisory PostgreSQL global y por transferencia impiden imports simultaneos.

## Estados y garantia de entrega

```text
UPLOADING -> READY -> IMPORTING -> VERIFIED
                 |         |
                 +---------+--> FAILED -> READY -> IMPORTING
```

- Repetir el mismo manifest devuelve la transferencia existente.
- Repetir una parte con igual offset, longitud y SHA devuelve
  `already_received`.
- Una colision de `transfer_id`, `chunk_id` o
  `(source_node_id, sequence)` con otra metadata devuelve `409`.
- Un fallo de complete conserva el archivo, marca FAILED y permite reintento.
- La clave unica de minutos `(lagoon_id, tag_id, bucket)` y el merge
  `ON CONFLICT DO NOTHING` hacen idempotente la importacion.
- Los eventos usan archivos separados y se reconcilian por UUID; nunca se
  mezclan con los minutos en un mismo CSV.

La garantia efectiva es at-least-once en transporte con efecto idempotente en
base de datos.

## Contrato HTTP

Rutas directas de FastAPI:

- `POST /offline-transfer/transfers`;
- `GET /offline-transfer/transfers/{transfer_id}`;
- `GET /offline-transfer/transfers/{transfer_id}/status`;
- `PUT /offline-transfer/transfers/{transfer_id}/parts/{part_number}`;
- `POST /offline-transfer/transfers/{transfer_id}/complete`.

Desde el Collector Offline a traves de IIS se usa
`https://crystalscada/api/offline-transfer/...`.

Todas las rutas requieren `Authorization: Bearer <token-de-nodo>`. El token se
guarda en el centro solamente como SHA-256. El `PUT` usa
`application/octet-stream`, `Content-Length`, `X-Part-Offset` y
`X-Part-SHA256`.

Header fijo de minutos:

```csv
lagoon_id,tag_id,bucket,state,value_num,value_bool,source
```

Header fijo de eventos:

```csv
id,lagoon_id,tag_id,tag_label,alert_type,previous_state,state,start_ts,end_ts,duration_sec,source
```

Los timestamps son UTC, los minutos estan alineados al minuto y las filas se
ordenan deterministamente. El importador rechaza headers alternativos, fuentes
distintas, tags desconocidos, duplicados internos y rangos que no coinciden con
el manifest.

## Frecuencia recomendada

La ingesta online conserva su frecuencia normal; el backfill no debe ejecutarse
como un batch diario. Al recuperar conectividad:

1. esperar un periodo corto de estabilidad;
2. registrar y enviar de inmediato un solo chunk activo;
3. consultar estado y continuar desde la primera parte faltante;
4. esperar `VERIFIED` antes de marcar o borrar el chunk local;
5. continuar con el siguiente chunk hasta vaciar el atraso.

El worker central consulta cada 5 segundos. Ante fallos usa backoff exponencial
de 15, 30, 60, 120, 240 y hasta 300 segundos, con un maximo de 10 intentos.
En el nodo se recomienda backoff con jitter y limite de ancho de banda para no
afectar la telemetria online. No se recomienda esperar una ventana nocturna
salvo que la red operacional tenga una restriccion explicita.

Como regla de dimensionamiento, el tamano del chunk se limita primero por 20.000
filas o 25 MiB sin comprimir. Si el atraso crece mas rapido de lo que se drena,
se debe medir
la tasa de generacion, el ancho de banda util y el tiempo de importacion antes de
aumentar concurrencia. La configuracion inicial mantiene una sola transferencia
activa por nodo.

## Instalacion central

No ejecutar estos pasos automaticamente en produccion. El orden de cutover es:

1. detener el emisor JSON antiguo del Collector Offline;
2. hacer backup y ejecutar `scripts/create_offline_transfer.sql` con
   el rol `userweb`;
3. configurar las variables `BACKFILL_*` del archivo
   `.env.example`;
4. crear el directorio durable y conceder acceso de escritura a la cuenta de los
   servicios, sin abrirlo a usuarios generales;
5. reiniciar el backend y hacer un smoke test con un chunk pequeno;
6. habilitar el nuevo uploader del nodo y observar hasta `VERIFIED`.

La migracion no contiene tokens en claro. El alta y rotacion de nodos se hace
por un administrador de base de datos. `userweb` puede leer nodos y actualizar
solo `last_seen_at/updated_at`; no puede crear nodos, borrar nodos ni cambiar
tokens.

No se instala worker, no se refrescan CAGG y no se modifica `scada_event` en
esta etapa. El contrato central acepta solo chunks `data_kind=minute`.

## Retencion, observabilidad y rollback

- Partes y archivo ensamblado se conservan siete dias despues de
  `VERIFIED`.
- La limpieza solo borra archivos bajo el storage configurado; mantiene
  manifests, estados, partes y contadores en PostgreSQL.
- Los archivos de `QUARANTINED` no se borran automaticamente.
- Alertar por transferencias en `FAILED`, `QUARANTINED`, leases vencidos,
  crecimiento del spool, latencia hasta `VERIFIED` y atraso local.

Para rollback se detienen primero el uploader nuevo y el worker. No se borran
tablas, archivos ni filas ya importadas. El endpoint online sigue independiente.
El emisor JSON antiguo solo debe reactivarse de forma deliberada para datos que
no llegaron a `VERIFIED`; no se deben ejecutar simultaneamente ambos
mecanismos sobre el mismo atraso.
