#!/bin/bash
# Carga año anterior + actual (los meses finales de un año se publican ya entrado el
# siguiente), con suelo en 2026 (inicio del proyecto).
. ~/.dbizi.env
Y0=$(( $(date -u +%Y) - 1 ))
[ "$Y0" -lt 2026 ] && Y0=2026
DBIZI_DSN="host=localhost dbname=dbizi user=dbizi password=$POSTGRES_PASSWORD" exec python3 ~/load_weather.py "$Y0"
