#!/bin/bash
# Regenera el JSON del timelapse desde Postgres y lo sube al bucket publico.
# La VM no abre ningun puerto: publica ficheros estaticos y ya.
# Cron cada 5 min. VENTANA_H controla cuantas horas se publican.
# PUBLICAR_HTML=1 regenera y sube tambien index.html (la pagina cambia poco:
# solo hace falta tras tocar la plantilla, el relieve o build_timelapse.py).
set -euo pipefail
. ~/.dbizi.env

VENTANA_H=${VENTANA_H:-24}
PUBLICAR_HTML=${PUBLICAR_HTML:-0}
BUCKET=gs://cosas-con-datos-en-dbizi-viz
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

# gcloud escribe su narracion por STDERR, asi que ">/dev/null" no la calla y
# "2>/dev/null" se tragaria los errores de verdad. Se captura y solo se habla
# si falla: exito en silencio, fallo integro en el log.
gcs() {
  local out
  if ! out=$(gcloud storage "$@" 2>&1); then printf '%s\n' "$out" >&2; return 1; fi
}

Q() { sudo docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" dbizi-postgres-1 \
        psql -U dbizi -d dbizi -tAF, -c "$1"; }

Q "SELECT station_id, name, ST_Y(geom), ST_X(geom), capacity
   FROM dbizi_station ORDER BY station_id;" > "$TMP/stations.csv"

# 4a columna: abierta = instalada y (presta o admite). Cerrada o averiada si no.
# 5a: bicis averiadas ancladas en la estacion (no cuentan en bikes_available).
# 6a: de las disponibles, cuantas son electricas (las mecanicas son el resto).
Q "SELECT station_id, to_char(ts AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS'), bikes_available,
          (coalesce(is_installed,true) AND (coalesce(is_renting,true) OR coalesce(is_returning,true))),
          coalesce(vehicles_disabled, 0), coalesce(electric_available, 0)
   FROM dbizi_measurement
   WHERE ts >= now() - interval '$VENTANA_H hours'
   ORDER BY ts, station_id;" > "$TMP/meas.csv"

# salud del feed: instante del último snapshot, cuándo lo capturamos y lo
# último que reportó alguna estación. Si ts se queda atrás y fetched_at no,
# el feed está parado y la web lo dice (si no, mostraría datos viejos como frescos).
Q "SELECT to_char(max(ts) AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS'),
          to_char(max(fetched_at) AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS'),
          to_char(max(last_reported) AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS')
   FROM dbizi_measurement WHERE ts >= now() - interval '2 hours';" > "$TMP/meta.csv"

# contexto: meteo horaria (Open-Meteo), festivos y la ultima cosecha de eventos
Q "SELECT to_char(ts AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS'), temperature, precipitation, wind_speed
   FROM weather_measurement
   WHERE station_id='OPENMETEO' AND ts >= now() - interval '$VENTANA_H hours' - interval '1 hour'
   ORDER BY ts;" > "$TMP/weather.csv"
Q "SELECT date, name FROM holiday WHERE date BETWEEN current_date - 3 AND current_date + 1;" > "$TMP/holidays.csv"
EVENTS=$(ls -1 ~/events/events_*.json.gz 2>/dev/null | tail -1)
Q "SELECT kind, name, to_char(starts_at AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS'),
          to_char(coalesce(ends_at, starts_at + interval '2 hours') AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS'),
          venue, lat, lon, confirmed
   FROM event
   WHERE starts_at BETWEEN now() - interval '$VENTANA_H hours' - interval '1 day' AND now() + interval '1 day'
   ORDER BY starts_at;" > "$TMP/events_db.csv"

python3 ~/build_timelapse.py "$TMP/stations.csv" "$TMP/meas.csv" \
  --geo ~/donostia-barrios.json --tpl ~/timelapse.tpl.html --json-only "$TMP/data.json" \
  --meta "$TMP/meta.csv" \
  --weather "$TMP/weather.csv" --holidays "$TMP/holidays.csv" ${EVENTS:+--events "$EVENTS"} \
  --events-db "$TMP/events_db.csv" > /dev/null

# gzip local (no "in flight"): asi el OBJETO queda comprimido y se sirve con
# content-encoding gzip. 75 KB pasan a 16 KB en el cable. Cache corta: el dato caduca rapido.
gcs cp -q --gzip-local-all --cache-control="public, max-age=60" \
  "$TMP/data.json" "$BUCKET/data.json"

if [ "$PUBLICAR_HTML" = 1 ]; then
  python3 ~/build_timelapse.py "$TMP/stations.csv" "$TMP/meas.csv" \
    --geo ~/donostia-barrios.json --tpl ~/timelapse.tpl.html --dem ~/donostia-dem.json \
    --src data.json --refresh 120 --out "$TMP/index.html"
  gcs cp -q --gzip-local-all --cache-control="public, max-age=300" \
    "$TMP/index.html" "$BUCKET/index.html"
fi
