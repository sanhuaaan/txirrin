#!/bin/bash
# Backup diario a GCS: dump de la BD (retención 7 días por lifecycle del bucket)
# + cosecha de eventos. El crudo de Dbizi ya no va aquí: lo sube raw_upload.sh
# cada hora, empaquetado por día (un objeto/día, dentro de la capa gratuita de
# operaciones de GCS). Cron: 04:10 UTC.
set -euo pipefail
. ~/.dbizi.env   # credenciales + HC_BACKUP (ping de healthchecks.io)

# gcloud escribe su narracion por STDERR, asi que ">/dev/null" no la calla y
# "2>/dev/null" se tragaria los errores de verdad. Se captura y solo se habla
# si falla: exito en silencio, fallo integro en el log.
gcs() {
  local out
  if ! out=$(gcloud storage "$@" 2>&1); then printf '%s\n' "$out" >&2; return 1; fi
}

BUCKET=gs://cosas-con-datos-en-dbizi-backup
STAMP=$(date -u +%Y%m%d)

sudo docker compose -f /opt/dbizi/docker-compose.yml exec -T postgres \
  pg_dump -U dbizi -Fc dbizi > "/tmp/dbizi_$STAMP.dump"
gcs cp -q "/tmp/dbizi_$STAMP.dump" "$BUCKET/dumps/"
rm "/tmp/dbizi_$STAMP.dump"

if [ -d "$HOME/events" ]; then
    gcs rsync -q -r "$HOME/events" "$BUCKET/events"
fi

# Todo subido: avisa al dead man's switch. Sin esto, un backup que deje de
# hacerse en silencio solo se descubre el día que hace falta restaurar.
[ -n "${HC_BACKUP:-}" ] && curl -fsS -m 10 "$HC_BACKUP" -o /dev/null 2>/dev/null || true
