#!/bin/bash
# Sube el crudo de Dbizi a GCS cada hora, empaquetado por dia: hoy y ayer, un
# objeto por dia que se sobreescribe (48 operaciones/dia, capa gratuita). Asi
# una VM perdida cuesta como mucho una hora de capturas, no un dia.
# Limpia el crudo local de mas de 30 dias (para entonces su tar lleva 30 dias
# subido). Cron: 5 * * * *
set -euo pipefail
. ~/.dbizi.env

gcs() {
  local out
  if ! out=$(gcloud storage "$@" 2>&1); then printf '%s\n' "$out" >&2; return 1; fi
}
BUCKET=${TXIRRIN_BUCKET_BACKUP:-gs://cosas-con-datos-en-dbizi-backup}   # en ~/.dbizi.env si es otro

python3 ~/pack_raw.py > /dev/null
for d in $(date -u -d yesterday +%Y%m%d) $(date -u +%Y%m%d); do
  [ -f ~/raw/$d.tar.xz ] && gcs cp -q ~/raw/$d.tar.xz "$BUCKET/raw/$d.tar.xz"
done

find ~/raw -maxdepth 1 -mindepth 1 -mtime +30 \( -type d -o -name '*.tar.*' \) -exec rm -rf {} +
