# Infraestructura — dónde corre el collector

El collector necesita una máquina siempre encendida. A 2026-08-20 no la hay; alternativas evaluadas:

## Estado actual: git-scraping (activo desde 2026-08-20) ✅

Sin servidor, coste cero: el repo público [`sanhuaaan/dbizi-raw`](https://github.com/sanhuaaan/dbizi-raw) captura los feeds GBFS (`station_status` + `station_information`) cada ~5 min con GitHub Actions y commitea el JSON — el histórico es el historial de git (mensaje de commit = timestamp UTC).

- Repo **público** a propósito: en privados los runners consumen los 2000 min/mes gratis en días; en públicos son ilimitados. El dato de Dbizi ya es público.
- Limitaciones: cron con jitter (retrasos de minutos, ticks perdidos ocasionales), mínimo 5 min. Vale para agregados horarios; para inferencia fina de flujos, no.
- **Disparador único: cron-job.org** (activo desde 2026-08-20, verificado): el cron nativo de Actions es best-effort (tardó ~30 min en arrancar y salta ticks; ya visto en otro proyecto), así que el disparo viene de [cron-job.org](https://cron-job.org) cada 5 min vía `workflow_dispatch`:
  - URL: `POST https://api.github.com/repos/sanhuaaan/dbizi-raw/actions/workflows/scrape.yml/dispatches`
  - Headers: `Authorization: Bearer <PAT>` · `Accept: application/vnd.github+json`
  - Body: `{"ref":"main"}`
  - PAT fine-grained solo con permiso **Actions: write** sobre `dbizi-raw` (se crea en github.com → Settings → Developer settings → Fine-grained tokens).
  - El `schedule` nativo **se eliminó el 2026-08-20**, tras medir que no aportaba: en las 3,4 h previas todos los ticks útiles llegaron por `workflow_dispatch` (mediana 5,0 min, 98% de cobertura) y el único run lanzado por `schedule` falló al colisionar con el dispatch 5 s anterior. Para reactivarlo, devolver el bloque `schedule` a `.github/workflows/scrape.yml`.
  - ⚠️ **Contrapartida**: cron-job.org pasa a ser punto único de fallo y su caída es silenciosa — si el PAT caduca o el servicio cae, la captura se detiene sin aviso y solo se detecta como hueco en el histórico. Mitigación pendiente: alerta si el último commit de `dbizi-raw` supera los ~20 min de antigüedad.
- Cuando exista la VM: backfill del historial de git a Postgres y el scraper queda como redundancia (o se apaga).

## Alternativas de VM

| Opción | Coste | Specs | Veredicto |
|--------|-------|-------|-----------|
| **Oracle Cloud Always Free** | 0 € | Hasta 4 vCPU ARM + 24 GB RAM + 200 GB | ❌ **Descartada 2026-08-20**: imposible completar el registro tras varios intentos (su verificación rechaza sin explicar; problema conocido) |
| **GCP `e2-micro`** | 0 € | 2 vCPU compartidas, 1 GB RAM, 30 GB standard PD, regiones EE. UU. (us-west1/central1/east1) | **← Elegida.** Free tier permanente (activar cuenta completa para que no pare a los 90 días; boot disk *standard*, no SSD). Justo pero cabe: Postgres + collector con `-Xmx256m` |
| **Hetzner** | ~4 €/mes | 2 vCPU, 4 GB | La salida honesta si los free tiers dan guerra. Cero fragilidad |
| **Raspberry Pi / mini-PC** | ~60 € una vez | — | En casa; suma electricidad (~1 €/mes) y depende de tu conexión |
| AWS / Azure free tier | 0 € temporal | — | ❌ Solo 12 meses o créditos; el proyecto vive años |
| Render / Railway / Fly | 0 € | — | ❌ Duermen servicios gratuitos o caducan la BD (Render: Postgres free 90 días) |

## Dimensionamiento (para no sobre-provisionar)

70 estaciones × captura cada 2 min ≈ 50k filas/día ≈ 18M filas/año. Postgres en 1 GB de RAM lo maneja; el crudo JSONB es lo único que abulta (~25 MB/día sin comprimir — TOAST comprime). Cualquier opción de la tabla sobra.

## VM (creada 2026-08-20) ✅

- **`dbizi-vm`** — e2-micro free tier, zona `us-west1-a`, Ubuntu 24.04, 30 GB pd-standard, IP pública efímera `34.53.18.193` (cambia si la VM se para/arranca).
- Proyecto GCP: `cosas-con-datos-en-dbizi` (cuenta personal). En local, configuración gcloud separada: `--configuration=dbizi` (la de trabajo `default` queda intacta).
- SSH: `gcloud compute ssh dbizi-vm --zone=us-west1-a --configuration=dbizi`
- **Alerta de presupuesto: 1 €** (avisa al 50% y 100%) sobre la cuenta de facturación. Vigilar el primer email: desde 2024 Google cobra las IPv4 externas en uso (~3 €/mes) y no está claro si exime al free tier — si aparece ese cargo, reevaluar (a ese precio, Hetzner da 4 GB de RAM).

## PostGIS en la VM (2026-08-20) ✅

- Docker + compose en `/opt/dbizi/` de la VM: contenedor `postgis/postgis:16-3.4`, `restart: always`, volumen `pgdata`.
- BD `dbizi`, usuario `dbizi`; contraseña en `/opt/dbizi/.env` de la VM (no está en este repo).
- Puerto 5432 **solo en localhost de la VM** — nada expuesto a internet. Acceso desde el portátil por túnel:

```bash
gcloud compute ssh dbizi-vm --zone=us-west1-a --configuration=dbizi -- -L 5432:localhost:5432 -N
# y en otra terminal: psql -h localhost -U dbizi dbizi
```

## Esquema e ingesta (2026-08-21) ✅

- Esquema mínimo en [`sql/schema.sql`](sql/schema.sql): `dbizi_station` (con `geom` PostGIS) + `dbizi_measurement` (PK `(station_id, ts)`, desglose mecánica/eléctrica). El crudo no se duplica en BD: vive en el historial de `dbizi-raw`.
- [`scripts/backfill.py`](scripts/backfill.py): recorre el historial git de `dbizi-raw` y carga snapshots. Re-ejecutable e incremental (estado del último commit procesado en `~/.dbizi_backfill_last` de la VM, `ON CONFLICT DO NOTHING`).
- Backfill inicial hecho: 229 snapshots / 16k filas (desde 2026-08-20 11:46 UTC).
- **Ingesta continua**: cron en la VM cada 10 min (`~/ingest.sh` → `git pull` + backfill incremental). Cadena completa: cron-job.org → Actions → git → VM → Postgres, latencia máx. ~15 min.

## Captura directa (2026-08-21) ✅ — arquitectura final

[`scripts/collect.py`](scripts/collect.py) en cron de la VM **cada 2 min**: GBFS → Postgres directo, sin intermediarios, y **crudo gzip a disco** (`~/raw/YYYYMMDD/`, ~1,1 MB/día — décadas de margen). `station_information` se refresca y archiva una vez al día. Reutiliza el parseo de `backfill.py`, que queda como herramienta de reparación de huecos.

Esquema ampliado y re-backfilleado desde el historial completo de git antes de retirar `dbizi-raw`: `vehicles_disabled` / `docks_disabled` / `bikes_overflow` (salud de estaciones) y `address` / `post_code`.

**Retirada de `dbizi-raw`** (decidida 2026-08-21, para frenar el crecimiento del almacenamiento en GitHub — crecía ~300-400 MB/año):

- [x] Job de cron-job.org parado y repo `sanhuaaan/dbizi-raw` borrado (usuario, 2026-08-21).
- [x] Cron `ingest.sh` retirado de la VM; el clon local `~/dbizi-raw` (804 KB) se conserva como archivo del histórico git y `backfill.py` sigue funcionando contra él (tolera la ausencia de remoto).
- ⚠️ La VM es ahora el único punto de captura; el crudo local y el backup pendiente a GCS son la red de seguridad.

## Plan

1. ✅ Git-scraping activo → **en retirada** (ver arriba).
2. ✅ VM GCP free tier creada y verificada por SSH.
3. ✅ PostGIS 3.4 / Postgres 16 en Docker en la VM.
4. ✅ Esquema + backfill del histórico de git.
5. ✅ Captura directa cada 2 min con crudo en disco (sustituye al collector Spring Boot: no aporta nada sobre esto en una VM de 1 GB).
6. Meteo: carga del histórico 10-min de C017 Miramón + notebook de exploración cuando haya ~2-3 semanas de datos.
7. Backup periódico `pg_dump` + `~/raw/` a GCS (5 GB free) — pendiente, gana importancia al retirar dbizi-raw.
