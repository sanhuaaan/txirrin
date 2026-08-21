# Infraestructura

Estado a 2026-08-21. Coste total: **0 €/mes**.

```text
  GBFS Dbizi          Euskalmet XML        Open-Meteo          Kulturklik
  (PBSC, 30s TTL)     (oficial, ~2 meses   (reanálisis         (eventos, la API
      │                de retraso)          horario, sin key)   purga el pasado)
      │ cada 2 min         │ mensual            │ diario            │ diario
      ▼                    ▼                    ▼                   ▼
┌──────────────── dbizi-vm · GCP e2-micro free tier · us-west1-a ────────────────┐
│                                                                                │
│  collect.py    load_weather.py    pull_openmeteo.py    harvest_events.py       │
│      │               │                   │                   │                 │
│      │               └───────┬───────────┘                   ▼                 │
│      ▼                       ▼                          ~/events/*.json.gz     │
│  Postgres 16 + PostGIS 3.4 (Docker, 5432 SOLO localhost)                       │
│      │                                                                         │
│      └── crudo Dbizi: ~/raw/YYYYMMDD/*.json.gz (~1 MB/día)                     │
│                                                                                │
│  backup.sh · 04:10 UTC                                                         │
└──────┬─────────────────────────────────────────────────────────────────────────┘
       ▼
  gs://cosas-con-datos-en-dbizi-backup
  (dumps/: 14 días · raw/ y events/: para siempre)
```

## VM

- **`dbizi-vm`**: e2-micro free tier (2 vCPU compartidas, 1 GB RAM, 30 GB pd-standard), Ubuntu 24.04, zona `us-west1-a`, scope `storage-rw`. IP efímera — no depender de ella.
- Proyecto GCP **`cosas-con-datos-en-dbizi`** (cuenta personal). Alerta de presupuesto: 1 € (email al 50%/100%).
- En local, todo con la configuración gcloud **`dbizi`** (la `default` del trabajo no se toca).
- ⚠️ Con 1 GB de RAM, las cargas masivas largas (multi-año) saturan la máquina hasta tumbar el SSH — cargar de año en año.

## Crons (crontab del usuario en la VM)

| Cron | Cuándo (UTC) | Qué hace | Log |
|------|--------------|----------|-----|
| `collect.sh` | cada 2 min | GBFS → `dbizi_measurement` + crudo gzip a `~/raw/` (`station_information` 1×/día) | `~/collect.log` |
| `backup.sh` | 04:10 diario | `pg_dump -Fc` → GCS `dumps/` + crudo de ayer → `raw/` + `~/events` → `events/` | `~/backup.log` |
| `weather.sh` | 04:45 día 2 de cada mes | Re-carga idempotente del año en curso de Euskalmet (XML oficiales) | `~/weather.log` |
| `harvest_events.py` | 05:20 diario | Kulturklik mes actual + siguiente → `~/events/events_YYYYMMDD.json.gz` | `~/events.log` |
| `openmeteo.sh` | 05:40 diario | Últimos 7 días horarios de Open-Meteo → `weather_measurement` (DO UPDATE: el modelo revisa) | `~/openmeteo.log` |

Los logs solo recogen errores (los scripts callan si todo va bien). Los `*.sh` son wrappers que cargan `~/.dbizi.env` (copia de las credenciales para cron).

## Tablas (BD `dbizi`, esquema en `sql/schema.sql`)

| Tabla | Contenido | Volumen (2026-08-21) |
|-------|-----------|----------------------|
| `dbizi_station` | 70 estaciones: `geom` PostGIS, capacidad, dirección, CP | 70 filas |
| `dbizi_measurement` | Snapshot cada 2 min por estación: bicis/anclajes disponibles, mecánica/eléctrica, **averiadas** (`vehicles_disabled`), anclajes rotos, overflow, flags. PK `(station_id, ts)` | 18,5k filas (desde 2026-08-20), ~50k/día |
| `weather_station` | `C017` (Miramón, pluviómetro oficial) y `OPENMETEO` (malla del mismo punto) | 2 filas |
| `weather_measurement` | `C017`: 10-min, ene→jun 2026 (lo último publicado). `OPENMETEO`: horaria, jul 2026→hoy. **Empalme sin hueco**; el análisis prefiere C017 donde exista | 26k + 1,2k filas |
| `holiday` | Festivos Donostia/Gipuzkoa a mano (`sql/holidays.sql`); añadir cada diciembre el año siguiente | 15 filas (2026) |

Los fuentes viven en este repo (`sql/`, `scripts/`) y se copian a la VM con `gcloud compute scp`. Crudo de eventos en `~/events/` (sin normalizar: la fase de eventos aún no ha llegado; se archiva porque Kulturklik purga el pasado).

## Backups y restauración

- **Qué**: dump diario `pg_dump -Fc` (retención 14 días, lifecycle del bucket) + crudo Dbizi del día anterior + cosechas de eventos (ambos permanentes; el crudo permite re-procesar cualquier campo no normalizado hoy).
- **Dónde**: `gs://cosas-con-datos-en-dbizi-backup` (us-west1, dentro de los 5 GB free).
- **Pérdida máxima asumida**: 24 h de snapshots.
- **Restauración** (VM muerta):
  1. Recrear VM (misma receta: e2-micro us-west1, scope `storage-rw`) + Docker + compose de `/opt/dbizi/` (recrear `.env` con contraseña nueva).
  2. `psql < sql/schema.sql && psql < sql/holidays.sql`
  3. `gcloud storage cp gs://.../dumps/<último>.dump . && pg_restore -U dbizi -d dbizi --data-only <dump>`
  4. `gcloud storage rsync -r gs://.../raw ~/raw` (y `events/` igual); re-instalar crons (tabla de arriba).
  5. El hueco entre dump y presente no es recuperable (Dbizi no ofrece histórico); la meteo sí rellena (Open-Meteo archive / XML oficial).

## Operación

```bash
# SSH
gcloud compute ssh dbizi-vm --zone=us-west1-a --configuration=dbizi

# Postgres desde el portátil (túnel; en otra terminal: psql -h localhost -U dbizi dbizi)
gcloud compute ssh dbizi-vm --zone=us-west1-a --configuration=dbizi -- -L 5432:localhost:5432 -N

# Salud: la última captura no debería superar ~4 min
# SELECT max(ts), now() - max(ts) FROM dbizi_measurement;

# Si el SSH da 255 en cadena: la VM está saturada (ver ⚠️ RAM) → gcloud compute instances reset
# (todo se auto-levanta: Docker restart:always + crons)
```

Credenciales BD: `/opt/dbizi/.env` (root, 600) y `~/.dbizi.env` (usuario, para cron). No están en el repo.

## Riesgos asumidos

- **La VM es el único punto de captura**: si muere, se pierden ≤24 h (hasta el último backup).
- **Free tier**: e2-micro en región US, disco *standard*, una VM. Vigilar el primer email de la alerta por el posible cargo de IPv4 (~3 €/mes); si aparece, reevaluar (Hetzner 4 €/mes, 4 GB).
- **Sin monitorización activa**: un collector caído solo se ve como hueco en `max(ts)`. Pendiente si duele: alerta de envejecimiento.
- **Meteo oficial con ~2 meses de retraso** (verificado): mitigado con Open-Meteo (reanálisis, no pluviómetro). API tiempo real de Euskalmet pendiente: su portal de registro no envía el correo de confirmación (reintentar algún día; si llega la key, añadir puller oficial y degradar Open-Meteo a respaldo).

## Historial de decisiones (condensado)

- **2026-08-20** — Arranque sin servidor: git-scraping en repo público `dbizi-raw` (Actions + cron-job.org al fallar el cron nativo de GitHub). Oracle Always Free descartada (registro imposible) → GCP e2-micro. PostGIS en Docker; backfill del historial git.
- **2026-08-21** — Captura directa cada 2 min con crudo a disco (el collector Spring Boot previsto quedó innecesario); esquema con salud de estaciones. **`dbizi-raw` y cron-job.org retirados** (crecimiento de GitHub); su clon queda en `~/dbizi-raw` de la VM como archivo. Backup diario a GCS. Capa de contexto: meteo (C017 **solo 2026** — 14 años ahogaban la VM y no aportaban frente a un histórico de bicis que nace en ago-2026 — + Open-Meteo para el desfase de publicación), festivos y cosecha diaria de Kulturklik.

## Siguiente hito

Primer notebook de exploración (túnel + pandas/plotly) cuando el histórico Dbizi tenga ~2-3 semanas (~primeros de septiembre 2026): perfiles por estación/hora/día-tipo y primer cruce con la lluvia, usando `holiday` para comparar días comparables.
