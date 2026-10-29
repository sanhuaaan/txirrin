#!/bin/bash
# Probabilidades del planificador de viajes -> plan.json en el bucket. Cron diario.
# Ultimas 8 semanas, por estacion x tipo de dia (lab/sab/dom; festivos = dom) x hora.
set -euo pipefail
. ~/.dbizi.env
BUCKET=${TXIRRIN_BUCKET_VIZ:-gs://cosas-con-datos-en-dbizi-viz}   # en ~/.dbizi.env si es otro
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

# --- marea por estacion x dia de la semana (festivo aparte) x hora para el reparto ---
# salidas/llegadas con la regla del timelapse (|delta|<6, abierta, <=5 min entre
# capturas) + fraccion vacia/llena + stock medio, por estacion, dia y hora.
Q "WITH m AS (
     SELECT station_id, ts, (ts AT TIME ZONE 'Europe/Madrid') AS lt, bikes_available, docks_available,
            bikes_available - lag(bikes_available) OVER w AS df,
            coalesce(vehicles_disabled,0) - lag(coalesce(vehicles_disabled,0)) OVER w AS db,
            (is_installed AND lag(is_installed) OVER w) AS inst, ts - lag(ts) OVER w AS gap
     FROM dbizi_measurement WHERE ts >= now() - interval '56 days'
     WINDOW w AS (PARTITION BY station_id ORDER BY ts))
   SELECT m.station_id,
          CASE WHEN h.date IS NOT NULL THEN 'fes'
               ELSE (ARRAY['lun','mar','mie','jue','vie','sab','dom'])[extract(isodow FROM m.lt)] END,
          extract(hour FROM m.lt)::int, m.lt::date,
          sum(CASE WHEN df IS NOT NULL AND inst AND gap <= interval '5 min' AND abs(df) < 6
                   THEN greatest(0, -df - greatest(0, db)) ELSE 0 END),
          sum(CASE WHEN df IS NOT NULL AND inst AND gap <= interval '5 min' AND abs(df) < 6
                   THEN greatest(0,  df - greatest(0,-db)) ELSE 0 END),
          avg((bikes_available = 0)::int), avg((docks_available = 0)::int), avg(bikes_available)
   FROM m LEFT JOIN holiday h ON h.date = m.lt::date
   WHERE m.lt >= now() - interval '56 days'
   GROUP BY 1, 2, 3, 4 HAVING count(*) >= 10 ORDER BY 1, 2, 3, 4;" > "$TMP/rates.csv"
Q "SELECT station_id, capacity, ST_Y(geom), ST_X(geom) FROM dbizi_station WHERE capacity IS NOT NULL;" > "$TMP/cap.csv"
# eventos con sitio (partidos, regatas, carreras): sus horas salen de la media y dan el perfil
Q "SELECT id, kind, to_char(starts_at AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS'),
          to_char(ends_at AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS'), lat, lon
   FROM event WHERE starts_at BETWEEN now() - interval '58 days' AND now() ORDER BY starts_at;" > "$TMP/events.csv"
python3 ~/build_rates.py "$TMP/rates.csv" "$TMP/cap.csv" "$TMP/events.csv" "$TMP/rates.json"
out=$(gcloud storage cp -q --gzip-local-all --cache-control="public, max-age=3600" \
  "$TMP/rates.json" "$BUCKET/rates.json" 2>&1) || { printf '%s\n' "$out" >&2; exit 1; }
