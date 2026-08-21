#!/bin/bash
# Backup diario a GCS: dump de la BD (retención 14 días por lifecycle del bucket)
# + crudo del día anterior (inmutable, se conserva siempre). Cron: 04:10 UTC.
set -euo pipefail

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
