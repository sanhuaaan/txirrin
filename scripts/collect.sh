#!/bin/bash
# Ping a healthchecks.io SOLO si la captura fue bien: dead man's switch.
# Si dejan de llegar pings (VM muerta, cron roto, Postgres caído, script reventado)
# salta el aviso. HC_COLLECT vive en ~/.dbizi.env, no en el repo.
. ~/.dbizi.env
cd ~
DBIZI_DSN="host=localhost dbname=dbizi user=dbizi password=$POSTGRES_PASSWORD" python3 ~/collect.py
rc=$?
# Best-effort: si el ping falla, healthchecks lo nota por ausencia; no ensuciamos el log.
[ $rc -eq 0 ] && [ -n "${HC_COLLECT:-}" ] && curl -fsS -m 10 "$HC_COLLECT" -o /dev/null 2>/dev/null
exit $rc
