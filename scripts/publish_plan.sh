#!/bin/bash
# Probabilidades del planificador de viajes -> plan.json en el bucket. Cron diario.
# Ultimas 8 semanas, por estacion x tipo de dia (lab/sab/dom; festivos = dom) x hora.
set -euo pipefail
. ~/.dbizi.env
BUCKET=gs://cosas-con-datos-en-dbizi-viz
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
Q() { sudo docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" dbizi-postgres-1 \
        psql -U dbizi -d dbizi -tAF, -c "$1"; }

Q "WITH m AS (
     SELECT station_id, (ts AT TIME ZONE 'Europe/Madrid') AS lt, bikes_available,
            docks_available, coalesce(electric_available, 0) AS el
     FROM dbizi_measurement
     WHERE is_installed AND coalesce(is_renting, true) AND ts >= now() - interval '56 days'),
   d AS (
     SELECT m.station_id, m.lt::date AS day,
            CASE WHEN h.date IS NOT NULL OR extract(isodow FROM m.lt) = 7 THEN 'dom'
                 WHEN extract(isodow FROM m.lt) = 6 THEN 'sab' ELSE 'lab' END AS dt,
            extract(hour FROM m.lt)::int AS hour,
            avg((bikes_available = 0)::int) AS pe, avg((docks_available = 0)::int) AS pf,
            avg((el = 0)::int) AS pn
     FROM m LEFT JOIN holiday h ON h.date = m.lt::date
     GROUP BY 1, 2, 3, 4 HAVING count(*) >= 10)
   SELECT station_id, dt, hour, sum(pe), sum(pf), sum(pn), count(*)
   FROM d GROUP BY 1, 2, 3 ORDER BY 1, 2, 3;" > "$TMP/plan.csv"
Q "SELECT to_char(date, 'YYYY-MM-DD') FROM holiday WHERE date >= current_date ORDER BY date;" > "$TMP/hol.csv"

python3 ~/build_plan.py "$TMP/plan.csv" "$TMP/hol.csv" "$TMP/plan.json"
out=$(gcloud storage cp -q --gzip-local-all --cache-control="public, max-age=3600" \
  "$TMP/plan.json" "$BUCKET/plan.json" 2>&1) || { printf '%s\n' "$out" >&2; exit 1; }
