#!/usr/bin/env python3
"""Captura directa GBFS -> Postgres, con crudo gzip a disco (~/raw/YYYYMMDD/).

Cron cada 2 min en la VM. Reutiliza el parseo/insert de backfill.py.
station_status en cada ejecución; station_information (estático) una vez al día.
Silencioso si todo va bien: el log solo recoge errores.

El crudo se escribe ANTES de tocar la BD a propósito: si Postgres falla (VM saturada),
el tick sigue en disco y scripts/ingest_raw.py lo reingesta después.
"""
import gzip
import json
import os
import urllib.request
from datetime import datetime, timezone

import psycopg2

from backfill import insert_stations, insert_status

BASE = "https://sansebastian.publicbikesystem.net/customer/gbfs/v3.0/"
RAW = os.path.expanduser("~/raw")
DSN = os.environ["DBIZI_DSN"]


def fetch(feed):
    """Devuelve (crudo, parseado). Valida antes de archivar: un 200 vacío o una página
    de error se comprimen igual de bien que un feed bueno (28 bytes de gzip válido)."""
    req = urllib.request.Request(BASE + feed, headers={"User-Agent": "dbizi-collector"})
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = r.read()
    data = json.loads(payload)
    if not data.get("data", {}).get("stations"):
        raise ValueError(f"{feed}: respuesta sin data.stations ({len(payload)} bytes)")
    return payload, data


def save_raw(now, name, payload):
    """Escritura atómica. gzip no vacía su búfer hasta close(), así que un proceso
    matado a mitad (la e2-micro se queda sin RAM) dejaba un .json.gz de 0 bytes que
    parecía un snapshot. Ahora eso deja un .tmp, que nadie confunde con un snapshot."""
    day_dir = os.path.join(RAW, now.strftime("%Y%m%d"))
    os.makedirs(day_dir, exist_ok=True)
    final = os.path.join(day_dir, f"{now.strftime('%H%M%S')}_{name}.json.gz")
    tmp = final + ".tmp"
    with gzip.open(tmp, "wb") as f:
        f.write(payload)
    os.replace(tmp, final)  # atómico dentro del mismo sistema de ficheros
    return day_dir


def main():
    now = datetime.now(timezone.utc)
    status_raw, status = fetch("station_status")
    day_dir = save_raw(now, "status", status_raw)

    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    if not any(f.endswith("_info.json.gz") for f in os.listdir(day_dir)):
        info_raw, info = fetch("station_information")
        save_raw(now, "info", info_raw)
        insert_stations(cur, info)
    insert_status(cur, status, fetched_at=now)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
