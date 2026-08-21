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

## Plan

1. ✅ Git-scraping activo (cron-job.org cada 5 min).
2. ✅ VM GCP free tier creada y verificada por SSH.
3. ✅ PostGIS 3.4 / Postgres 16 en Docker en la VM.
4. Esquema mínimo + backfill del historial de `dbizi-raw` a Postgres.
5. Collector real (Spring Boot) en la VM; git-scraping queda de redundancia.
