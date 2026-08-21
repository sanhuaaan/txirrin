# Infraestructura

Estado a 2026-08-21. Coste: **0 €/mes**.

```text
  GBFS Dbizi        Euskalmet XML      Open-Meteo        Kulturklik
  (PBSC, 30s TTL)   (~2 meses de       (reanálisis       (eventos; la API
                     retraso)           horario)          purga el pasado)
      │ 2 min            │ mensual          │ diario          │ diario
      ▼                  ▼                  ▼                 ▼
┌─────────────── dbizi-vm · GCP e2-micro free tier · us-west1-a ───────────────┐
│                                                                             │
│  collect.py   load_weather.py   pull_openmeteo.py   harvest_events.py       │
│      │              └───────┬──────────┘                  │                 │
│      ▼                      ▼                             ▼                 │
│  ~/raw/*.json.gz   Postgres 16 + PostGIS 3.4        ~/events/*.json.gz      │
│  (crudo, atómico)  (Docker, 5432 SOLO localhost)                            │
│      │                   │        │                       │                 │
│      │                   │        └── publish_viz.sh ─┐   │                 │
│      └───────────────────┴── backup.sh ──┐            │   │                 │
└──────────────────────────────────────────┼────────────┼───┼─────────────────┘
                                           ▼            ▼   ▼
              gs://…-backup  (PRIVADO)        gs://…-viz  (PÚBLICO)
              dumps/ 7 días                   index.html + data.json
              raw/ y events/ para siempre      → la web viva del timelapse

  Vigilancia: collect.sh y backup.sh pingan a healthchecks.io al terminar bien.
  Su ausencia es la alarma.
```

## VM

- **`dbizi-vm`**: e2-micro free tier (2 vCPU compartidas, 1 GB RAM, 30 GB pd-standard), Ubuntu 24.04, `us-west1-a`. Scopes: `devstorage.read_write` y `logging.write`. IP efímera — no depender de ella.
- Proyecto GCP **`cosas-con-datos-en-dbizi`** (cuenta personal). Alerta de presupuesto: 1 € (email al 50%/100%).
- En local, todo con la configuración gcloud **`dbizi`** (la `default` del trabajo no se toca).
- Los fuentes van **planos a `~`**: en la VM no hay subdirectorios, así que los scripts que necesitan la plantilla o la geometría reciben la ruta por argumento.
- ⚠️ **Con 1 GB de RAM, las cargas masivas largas (multi-año) saturan la máquina hasta tumbar el SSH** — cargar de año en año. El 2026-08-21, durante la carga inicial multi-año de Euskalmet, el collector murió a mitad de escritura y dejó un `~/raw/20260821/080401_status.json.gz` de **0 bytes** (gzip no vacía su búfer hasta `close()`, así que un payload vacío bien cerrado ocupa 28 bytes y 0 solo sale de una muerte a media escritura). Desde entonces el crudo se escribe a `.tmp` y se renombra: un proceso matado deja un `.tmp`, nunca un `.json.gz` que parezca un snapshot.

## Buckets

| Bucket | Acceso | Contiene | Caducidad |
|--------|--------|----------|-----------|
| `cosas-con-datos-en-dbizi-backup` | **privado** | `dumps/`, `raw/`, `events/` | solo `dumps/`, 7 días |
| `cosas-con-datos-en-dbizi-viz` | **público** | `index.html`, `data.json` | ninguna (se sobrescriben) |

Están separados **a propósito**: en GCS los permisos públicos son a nivel de bucket, así que publicar la web desde el de backups habría hecho públicos los dumps de la base de datos. La regla de caducidad va acotada con `matchesPrefix: ["dumps/"]` — sin ese acote se llevaría por delante el crudo, que es irrecuperable. Ninguno tiene versionado, así que sobrescribir `data.json` no acumula copias.

## Crons (crontab del usuario en la VM)

| Cron | Cuándo (UTC) | Qué hace | Log |
|------|--------------|----------|-----|
| `collect.sh` | cada 2 min | GBFS → `dbizi_measurement` + crudo gzip a `~/raw/` (`station_information` 1×/día). Valida el feed antes de archivar y escribe de forma atómica | `~/collect.log` |
| `publish_viz.sh` | cada 5 min (`:02`, `:07`…) | Regenera el JSON del timelapse (24 h) → bucket público | `~/viz.log` |
| `backup.sh` | 04:10 diario | `pg_dump -Fc` → `dumps/` + crudo de ayer → `raw/` + `~/events` → `events/` | `~/backup.log` |
| `weather.sh` | 04:45 del día 2 de cada mes | Euskalmet oficial, idempotente: **año anterior + actual** (suelo en 2026). Los meses ya cargados insertan 0; los no publicados dan 404 y se saltan | `~/weather.log` |
| `harvest_events.py` | 05:20 diario | Kulturklik mes actual + siguiente → `~/events/events_YYYYMMDD.json.gz` | `~/events.log` |
| `openmeteo.sh` | 05:40 diario | Últimos 7 días horarios → `weather_measurement` (DO UPDATE: el modelo revisa) | `~/openmeteo.log` |

**Los logs solo recogen errores**: los scripts callan cuando todo va bien, y por eso un log con contenido es señal de que algo pasó. Ojo con `gcloud`, que narra por **stderr**: los scripts que suben a GCS envuelven la llamada para capturarla y hablar solo si falla (`>/dev/null` no la calla y `2>/dev/null` se tragaría los errores de verdad). Verificado en las condiciones del cron: éxito 0 bytes, fallo con el `ERROR` íntegro.

`~/collect.log` conserva un traceback del 2026-08-21 07:26 — el `OperationalError` cuyos 3 snapshots recuperó `ingest_raw.sh`. Se deja como evidencia.

El cron de visualización va a **minutos impares** para no coincidir con el collector, que va a pares.

## Herramientas que no son cron

- **`ingest_raw.sh [YYYYMMDD ...]`** — la red de seguridad. Si Postgres estuvo caído, el crudo sigue en disco y esto lo reingesta: idempotente, salta ficheros truncados o vacíos, y rellena `fetched_at` desde el nombre del fichero. Estrenado el 2026-08-21 recuperando 3 snapshots perdidos por un `OperationalError` del collector.
- **`openmeteo.sh <días>` o `<inicio> <fin>`** — rehace huecos de meteo reciente. Con dos fechas usa la API de archivo, que va ~2 días por detrás; para lo más reciente, la forma de días (máx. 92).
- **`ingest.sh`** — equivalente para el clon git de `dbizi-raw` (`backfill.py`). Solo valor histórico: ese repo está retirado.
- **`build_timelapse.py`** — genera el timelapse en sus dos variantes (ver más abajo).

## Tablas (BD `dbizi`, esquema en `sql/schema.sql`)

| Tabla | Contenido | Volumen (2026-08-21) |
|-------|-----------|----------------------|
| `dbizi_station` | 70 estaciones: `geom` PostGIS, capacidad, dirección, CP | 70 filas |
| `dbizi_measurement` | Snapshot cada 2 min por estación: bicis/anclajes, mecánica/eléctrica, **averiadas**, anclajes rotos, overflow, flags. `ts` = `last_updated` del feed; `fetched_at` = captura real. PK `(station_id, ts)` | 37,7k filas (desde 2026-08-20), ~50k/día |
| `weather_station` | `C017` (Miramón, pluviómetro oficial) y `OPENMETEO` (malla del mismo punto) | 2 filas |
| `weather_measurement` | `C017` 10-min ene→jun 2026 · `OPENMETEO` horaria jul→hoy. Empalme sin hueco; el análisis prefiere C017 donde exista | 26.064 + 1.240 filas |
| `holiday` | Festivos Donostia/Gipuzkoa a mano; añadir cada diciembre el siguiente | 15 filas (2026) |

Dos trampas del modelo, ambas documentadas en el propio `schema.sql`:

- **`weather_measurement.precipitation` son mm acumulados en `interval_minutes`**, que vale 10 para C017 y 60 para Open-Meteo. Los totales diarios salen bien en cada serie, pero comparar umbrales entre ellas exige normalizar: `precipitation * 60.0 / interval_minutes`.
- **`mechanical_available + electric_available` no siempre cuadra con `bikes_available`** (visto en ~1 de 70 estaciones): PBSC reporta `vehicle_types_available` desacompasado. No apilar sobre el total.

`fetched_at` existe para distinguir **collector caído** (deja de avanzar) de **feed de PBSC congelado** (`ts` se para pero `fetched_at` sigue). Las filas que vienen del backfill del historial git lo tienen a NULL, porque de esas no se conoce la hora real de captura.

## Despliegue

`sql/schema.sql` es **re-ejecutable**: sus `ALTER ... IF NOT EXISTS` finales migran una BD ya poblada. Copiar y relanzar:

```bash
gcloud compute scp sql/schema.sql scripts/*.py scripts/*.sh \
  viz/donostia-barrios.json viz/timelapse.tpl.html \
  dbizi-vm:~/ --zone=us-west1-a --configuration=dbizi

gcloud compute ssh dbizi-vm --zone=us-west1-a --configuration=dbizi --command='. ~/.dbizi.env
  sudo docker exec -i -e PGPASSWORD="$POSTGRES_PASSWORD" dbizi-postgres-1 \
    psql -U dbizi -d dbizi -v ON_ERROR_STOP=1 -f - < ~/schema.sql'
```

**Migrar el esquema antes de copiar los `.py`**: el collector corre cada 2 min y fallaría al escribir una columna que aún no existe. Y no olvidar los dos ficheros de `viz/`: sin ellos `publish_viz.sh` no arranca.

## Web viva del timelapse

**https://storage.googleapis.com/cosas-con-datos-en-dbizi-viz/index.html** (la raíz sin `/index.html` devuelve el listado XML del bucket, no la página).

- `publish_viz.sh` consulta Postgres, regenera el JSON con ventana de 24 h y lo sube. La página lo recarga cada 2 min y muestra la edad del último dato.
- **La VM no abre ningún puerto.** Postgres sigue en localhost; lo que se publica son ficheros estáticos, así que no hay superficie de ataque nueva. El precio es el retardo del cron: en el peor caso ves algo de hace ~7 min contando el propio muestreo.
- Todo se sube con `--gzip-local-all`, no `--gzip-in-flight-all`: el primero deja el **objeto** comprimido, el segundo solo el transporte de subida. Página 26 KB → 9,8 KB; JSON 75 KB → 16 KB.
- `VENTANA_H=48 ~/publish_viz.sh` publica más horas.
- Si cambia el conjunto de estaciones, la página se recarga sola en el siguiente refresco.
- El **artefacto de Claude** es una variante distinta del mismo `viz/timelapse.tpl.html`, con los datos incrustados: una foto congelada compartible. No puede estar en vivo porque su CSP bloquea todo `fetch` externo y las capacidades disponibles no incluyen ninguna de red.

## Monitorización

Dead man's switch en [healthchecks.io](https://healthchecks.io) (plan gratuito): los scripts pingan **solo si terminan bien**, así que la ausencia de ping es la señal. Cubre de una vez VM apagada, cron roto, Postgres caído y script reventado — incluido el caso en que un monitor dentro de la VM no podría avisar de nada.

| Check | Periodo | Gracia | Salta si |
|-------|---------|--------|----------|
| `dbizi-collect` | 2 min | 20 min | el collector lleva ~22 min sin capturar |
| `dbizi-backup` | 1 día | 2 h | el backup diario no se hizo |

- Alertas **one-shot**: un correo al caer y otro al recuperarse, no un goteo. Verificado a mano el 2026-08-21 con `curl "$HC_COLLECT/fail"` — llegaron los dos, y lo del correo de recuperación no está documentado por healthchecks.
- La gracia ancha es deliberada: un tick suelto que falle **ya no pierde datos** (queda el crudo, y `ingest_raw.sh` lo recupera), así que solo interesa enterarse de caídas sostenidas.
- Las URLs de ping son secretas: viven en `~/.dbizi.env` como `HC_COLLECT` y `HC_BACKUP`. El repo solo referencia las variables, y si no están definidas los scripts funcionan igual sin pingar.
- **No cubre el feed congelado** de PBSC: `collect.py` termina bien aunque `last_updated` no avance. Para eso, el chequeo manual de abajo.

## Almacenamiento y crecimiento

| Qué | Ahora | Al año | ¿Acumula? |
|-----|-------|--------|-----------|
| `dbizi_measurement` | 6,5 MB · 37,7k filas | ~3,2 GB | sí (176 B/fila, 50,4k filas/día) |
| Crudo `~/raw` | 1,3 MB | ~1,1 GB | sí, y se sube a GCS para siempre |
| Eventos | 428 KB | ~156 MB | sí (recosecha completa diaria, redundante) |
| `dumps/` en GCS | 0,8 MB | ~1,6 GB | rota a 7 días |
| `data.json` del timelapse | 25 KB | 25 KB | **no**, se sobrescribe |

- **Disco**: 3,8 GB de 29 usados (14%) → unos **7 años** de margen.
- **GCS**: ~2,9 GB al primer año, dentro de los 5 GB del free tier.
- **Por qué 7 días de dumps y no 14**: `raw/` se conserva indefinidamente y es la fuente real — `ingest_raw.sh` reconstruye la tabla desde ahí. Catorce copias completas de una base que crece eran el 70% de la huella en GCS sin cubrir nada que el crudo no cubra.
- `weather_measurement` ocupa 888 B/fila frente a los 116 de `dbizi_measurement`: no es corrupción ni filas muertas, es espacio libre que dejó la carga multi-año descartada. Se irá rellenando solo con la meteo que entra; un `VACUUM FULL` recuperaría ~35 MB pero bloquea la tabla y no compensa en un disco de 29 GB.

## Backups y restauración

- **Qué**: dump diario `pg_dump -Fc` (7 días) + crudo del día anterior + cosechas de eventos (estos dos, permanentes: el crudo permite reprocesar cualquier campo no normalizado hoy).
- **Pérdida máxima asumida**: 24 h de snapshots en la BD — pero el crudo del día en curso sigue en el disco de la VM, así que solo se pierde de verdad si muere la máquina entera.
- **Restauración** (VM muerta):
  1. Recrear VM (e2-micro `us-west1-a`, scopes `devstorage.read_write` y `logging.write`) + Docker + compose de `/opt/dbizi/`, con `.env` de contraseña nueva.
  2. Recrear `~/.dbizi.env`: `POSTGRES_PASSWORD`, `HC_COLLECT`, `HC_BACKUP` (las dos últimas, del panel de healthchecks.io).
  3. Copiar fuentes con el bloque de **Despliegue** y lanzar `schema.sql` y `holidays.sql`.
  4. `gcloud storage cp gs://…/dumps/<último>.dump . && pg_restore -U dbizi -d dbizi --data-only <dump>`
  5. `gcloud storage rsync -r gs://…/raw ~/raw` (y `events/` igual), luego `~/ingest_raw.sh` para tapar lo que el dump no alcance.
  6. Reinstalar los crons de la tabla de arriba.
  7. El hueco de Dbizi entre dump y presente solo se recupera si estaba en `raw/`; la meteo sí se rehace con `openmeteo.sh` y `weather.sh`.
- ⚠️ **La restauración nunca se ha ensayado de punta a punta.**

## Operación

```bash
# SSH
gcloud compute ssh dbizi-vm --zone=us-west1-a --configuration=dbizi

# Postgres desde el portátil (túnel; en otra terminal: psql -h localhost -U dbizi dbizi)
gcloud compute ssh dbizi-vm --zone=us-west1-a --configuration=dbizi -- -L 5432:localhost:5432 -N

# Salud: ninguna de las dos debería superar ~4 min.
# fetched_at parado = collector caído; ts parado con fetched_at vivo = feed de PBSC congelado.
# SELECT now() - max(fetched_at) AS desde_captura,
#        now() - max(ts)         AS desde_dato_feed FROM dbizi_measurement;

# Si el SSH da 255 en cadena: la VM está saturada (ver ⚠️ RAM) → gcloud compute instances reset
# (todo se auto-levanta: Docker restart:always + crons)
```

Credenciales BD: `/opt/dbizi/.env` (root, 600) y `~/.dbizi.env` (usuario, para cron). **No están en el repo.**

## Riesgos asumidos

- **La VM es el único punto de captura**: si muere, se pierde lo que no llegara al último backup.
- **Free tier**: e2-micro en región US, disco *standard*, una VM. Vigilar el primer email de la alerta por el posible cargo de IPv4 (~3 €/mes); si aparece, reevaluar (Hetzner 4 €/mes, 4 GB).
- **La web del timelapse es pública sin autenticación**: cualquiera con la URL entra. Hoy da igual —el dato de Dbizi ya es público— pero condiciona lo que se pueda poner ahí.
- **Meteo oficial con ~2 meses de retraso** (verificado: en agosto lo último publicado era junio): mitigado con Open-Meteo, que es reanálisis, no pluviómetro. La API en tiempo real de Euskalmet sigue pendiente porque su portal no envía el correo de confirmación; si algún día llega la key, añadir puller oficial y degradar Open-Meteo a respaldo.
- **Restauración sin ensayar.**

## Historial de decisiones (condensado)

- **2026-08-20** — Arranque sin servidor: git-scraping en el repo público `dbizi-raw` (Actions, con cron-job.org al fallar el cron nativo de GitHub). Oracle Always Free descartada (registro imposible) → GCP e2-micro. PostGIS en Docker; backfill del historial git.
- **2026-08-21 (mañana)** — Captura directa cada 2 min con crudo a disco: el collector Spring Boot previsto quedó innecesario. **`dbizi-raw` y cron-job.org retirados**; su clon queda en `~/dbizi-raw` como archivo. Backup diario a GCS. Capa de contexto: meteo (C017 **solo 2026** — 14 años ahogaban la VM y no aportaban frente a un histórico de bicis que nace en agosto — más Open-Meteo para el desfase de publicación), festivos y cosecha diaria de Kulturklik.
- **2026-08-21 (tarde)** — Revisión de código y consolidación:
  - Esquema con `fetched_at` e `interval_minutes`; `ingest_raw.sh` para reingestar el crudo; wrappers de cron versionados en el repo.
  - Corregido `parse_ts`, que reventaba con las fracciones de segundo recortadas de PBSC y tiraba snapshots enteros en Python <3.11.
  - Escritura atómica del crudo tras el fichero de 0 bytes.
  - `pull_openmeteo.py` con ventana configurable, para que rehacer un hueco sea reproducible.
  - **Monitorización** con dead man's switch, probada forzando una caída real.
  - **Timelapse isométrico**: artefacto congelado + **web viva** en bucket público propio.
  - Retención de dumps de 14 a 7 días.

## Siguiente hito

Primer notebook de exploración (túnel + pandas/plotly) cuando el histórico Dbizi tenga ~2-3 semanas (~primeros de septiembre 2026): perfiles por estación/hora/día-tipo y primer cruce con la lluvia, usando `holiday` para comparar días comparables.
