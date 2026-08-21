# Infraestructura

Estado a 2026-08-21. Coste total: **0 €/mes**.

```text
GBFS Dbizi (PBSC, público, sin auth)
https://sansebastian.publicbikesystem.net/customer/gbfs/v3.0/
        │
        │  cron cada 2 min (collect.sh)
        ▼
┌─────────────────── dbizi-vm · GCP e2-micro free tier · us-west1-a ───────────────────┐
│                                                                                      │
│  collect.py ──► Postgres 16 + PostGIS 3.4 (Docker, 5432 SOLO localhost)              │
│       │                                                                              │
│       └──────► ~/raw/YYYYMMDD/*.json.gz   (crudo gzip, ~1 MB/día)                    │
│                                                                                      │
│  backup.sh · cron 04:10 UTC                                                          │
└──────┬───────────────────────────────────────────────────────────────────────────────┘
       ▼
  gs://cosas-con-datos-en-dbizi-backup   (dumps: retención 14 días · raw: para siempre)
```

## Componentes

| Pieza | Qué es | Dónde |
|-------|--------|-------|
| **VM `dbizi-vm`** | e2-micro free tier (2 vCPU compartidas, 1 GB RAM, 30 GB pd-standard), Ubuntu 24.04, zona `us-west1-a`, scope `storage-rw`. IP efímera — no depender de ella | Proyecto GCP `cosas-con-datos-en-dbizi` (cuenta personal) |
| **Postgres 16 + PostGIS 3.4** | Docker (`postgis/postgis:16-3.4`), `restart: always`, volumen `pgdata`, puerto solo en localhost | `/opt/dbizi/` (compose + `.env` con credenciales, root 600) |
| **`collect.py`** | Captura directa: `station_status` → BD + crudo gzip; `station_information` 1×/día. Silencioso si todo va bien | `~/collect.py` en la VM, cron `*/2` vía `~/collect.sh` |
| **`backfill.py`** | Reparación de huecos: reprocesa snapshots desde el clon git archivado. Comparte parseo con collect | `~/backfill.py`; archivo histórico en `~/dbizi-raw` (804 KB, sin remoto) |
| **`backup.sh`** | `pg_dump -Fc` → `dumps/` (el bucket borra a los 14 días) + crudo de ayer → `raw/YYYYMMDD/` (permanente) | `~/backup.sh`, cron `10 4 * * *` UTC |
| **Bucket GCS** | `cosas-con-datos-en-dbizi-backup`, us-west1, uniform access, lifecycle 14 d sobre `dumps/` | Dentro de los 5 GB free tier |
| **Alerta de presupuesto** | 1 € (email al 50% y 100%) en la cuenta de facturación | Consola GCP |

Los fuentes de los scripts viven en este repo (`sql/`, `scripts/`) y se copian a la VM con `gcloud compute scp`.

## Operación

Todo con la configuración gcloud **`dbizi`** (cuenta personal `jsanjuan83@gmail.com`; la configuración `default` del trabajo no se toca):

```bash
# SSH a la VM
gcloud compute ssh dbizi-vm --zone=us-west1-a --configuration=dbizi

# Postgres desde el portátil (túnel; en otra terminal: psql -h localhost -U dbizi dbizi)
gcloud compute ssh dbizi-vm --zone=us-west1-a --configuration=dbizi -- -L 5432:localhost:5432 -N

# Salud rápida: última captura (no debería superar ~4 min de antigüedad)
# SELECT max(ts), now() - max(ts) FROM dbizi_measurement;

# Logs de los crons en la VM: ~/collect.log y ~/backup.log (solo errores)
```

Credenciales de BD: `/opt/dbizi/.env` (root) y copia `~/.dbizi.env` (para los crons). No están en el repo.

## Datos

- `dbizi_station` — 70 estaciones con `geom` PostGIS, capacidad, dirección.
- `dbizi_measurement` — un registro por estación y snapshot (~50k filas/día a ritmo de 2 min): bicis/anclajes disponibles, desglose mecánica/eléctrica, **averiadas** (`vehicles_disabled`), anclajes rotos, overflow, flags de estado. Histórico desde 2026-08-20 11:46 UTC sin huecos relevantes.
- Crudo completo en `~/raw/` (VM) + copia diaria en GCS: cualquier campo no normalizado hoy es re-procesable mañana.

## Riesgos asumidos

- **La VM es el único punto de captura.** Si muere, se pierden como máximo 24 h (hasta el último backup). Recuperación: recrear VM + restaurar dump + `~/raw` de GCS.
- **Condiciones del free tier**: e2-micro en región US, disco *standard*, una sola VM. Vigilar el primer email de la alerta por el posible cargo de IPv4 externa (~3 €/mes); si aparece, reevaluar (Hetzner 4 €/mes, 4 GB RAM).
- Sin monitorización activa: una caída del collector solo se ve como hueco en `max(ts)`. Pendiente si algún día duele: alerta si la última captura envejece.

## Historial de decisiones (condensado)

- **2026-08-20** — Arranque sin servidor: git-scraping en repo público `dbizi-raw` (Actions cada 5 min). El cron nativo de GitHub resultó poco fiable → disparo externo desde cron-job.org. Oracle Always Free descartada (registro imposible); elegida GCP e2-micro. PostGIS en Docker en la VM; backfill del historial git (233 snapshots).
- **2026-08-21** — Captura directa `collect.py` cada 2 min con crudo a disco (el collector Spring Boot previsto quedó innecesario). Esquema ampliado con salud de estaciones y re-backfill completo. **`dbizi-raw` y cron-job.org retirados** (evitar crecimiento de almacenamiento en GitHub); su clon queda en la VM como archivo. Backup diario a GCS.

## Siguiente hito

Ya no es infra: cargar histórico meteo 10-min de **C017 Miramón** (Euskalmet) y primer notebook de exploración cuando haya ~2-3 semanas de datos.
