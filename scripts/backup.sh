#!/bin/bash
# Backup diario a GCS: dump de la BD (retención 14 días por lifecycle del bucket)
# + crudo del día anterior (inmutable, se conserva siempre). Cron: 04:10 UTC.
set -euo pipefail
. ~/.dbizi.env   # credenciales + HC_BACKUP (ping de healthchecks.io)

BUCKET=gs://cosas-con-datos-en-dbizi-backup
STAMP=$(date -u +%Y%m%d)

sudo docker compose -f /opt/dbizi/docker-compose.yml exec -T postgres \
  pg_dump -U dbizi -Fc dbizi > "/tmp/dbizi_$STAMP.dump"
gcloud storage cp -q "/tmp/dbizi_$STAMP.dump" "$BUCKET/dumps/"
rm "/tmp/dbizi_$STAMP.dump"

YESTERDAY=$(date -u -d yesterday +%Y%m%d)
if [ -d "$HOME/raw/$YESTERDAY" ]; then
    gcloud storage rsync -q -r "$HOME/raw/$YESTERDAY" "$BUCKET/raw/$YESTERDAY"
fi

if [ -d "$HOME/events" ]; then
    gcloud storage rsync -q -r "$HOME/events" "$BUCKET/events"
fi

# Todo subido: avisa al dead man's switch. Sin esto, un backup que deje de
# hacerse en silencio solo se descubre el día que hace falta restaurar.
[ -n "${HC_BACKUP:-}" ] && curl -fsS -m 10 "$HC_BACKUP" -o /dev/null 2>/dev/null || true
