#!/bin/bash
. ~/.dbizi.env
cd ~
DBIZI_DSN="host=localhost dbname=dbizi user=dbizi password=$POSTGRES_PASSWORD" exec python3 ~/collect.py
