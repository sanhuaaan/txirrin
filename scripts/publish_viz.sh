#!/bin/bash
# Regenera el JSON del timelapse desde Postgres y lo sube al bucket publico.
# La VM no abre ningun puerto: publica ficheros estaticos y ya.
# Cron cada 5 min. VENTANA_H controla cuantas horas se publican.
set -euo pipefail
. ~/.dbizi.env

VENTANA_H=${VENTANA_H:-24}
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

Q "SELECT station_id, to_char(ts AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS'), bikes_available
   FROM dbizi_measurement
   WHERE ts >= now() - interval '$VENTANA_H hours'
   ORDER BY ts, station_id;" > "$TMP/meas.csv"

python3 ~/build_timelapse.py "$TMP/stations.csv" "$TMP/meas.csv" \
  --geo ~/donostia-barrios.json --tpl ~/timelapse.tpl.html \
  --json-only "$TMP/data.json" > /dev/null

# gzip local (no "in flight"): asi el OBJETO queda comprimido y se sirve con
# content-encoding gzip. 75 KB pasan a 16 KB en el cable. Cache corta: el dato caduca rapido.
gcs cp -q --gzip-local-all --cache-control="public, max-age=60" \
  "$TMP/data.json" "$BUCKET/data.json"
