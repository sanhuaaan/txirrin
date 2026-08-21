#!/bin/bash
. ~/.dbizi.env
DBIZI_DSN="host=localhost dbname=dbizi user=dbizi password=$POSTGRES_PASSWORD" exec python3 ~/pull_openmeteo.py
