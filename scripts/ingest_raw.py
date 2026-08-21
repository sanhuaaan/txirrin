#!/usr/bin/env python3
"""Reingesta el crudo de disco (~/raw/YYYYMMDD/*.json.gz) a Postgres.

collect.py guarda el crudo ANTES de tocar la BD, así que un fallo de Postgres
(VM saturada, contenedor caído) deja el tick en disco pero no en la tabla.
Este script lo recupera. También rellena fetched_at (la hora real de captura va
en el nombre del fichero) en las filas que se insertaron sin ella.

Idempotente (ON CONFLICT DO NOTHING): re-ejecutable sin duplicar.
Commit por día para no inflar la transacción en la e2-micro.

Uso: DBIZI_DSN=... ./ingest_raw.py [YYYYMMDD ...]   (sin args: todos los días)
     DBIZI_RAW_DIR: raíz del crudo (por defecto ~/raw)
"""
import gzip
import json
import os
import sys
from datetime import datetime, timezone

import psycopg2

from backfill import insert_stations, insert_status, parse_ts

RAW = os.environ.get("DBIZI_RAW_DIR", os.path.expanduser("~/raw"))
DSN = os.environ["DBIZI_DSN"]


def fetched_at_from(day, fname):
    """~/raw/20260820/151143_status.json.gz -> datetime UTC de la captura."""
    hhmmss = fname.split("_", 1)[0]
    return datetime.strptime(day + hhmmss, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)


def read_gz(path):
    with gzip.open(path, "rb") as f:
        return json.loads(f.read())


def process_day(cur, day):
    day_dir = os.path.join(RAW, day)
    inserted = backfilled = skipped = 0
    for fname in sorted(os.listdir(day_dir)):
        if not fname.endswith(".json.gz"):
            continue
        path = os.path.join(day_dir, fname)
        try:
            feed = read_gz(path)
        except (OSError, ValueError, EOFError) as e:  # truncado por un corte a mitad de escritura
            # gzip lanza EOFError si falta el marcador de fin y BadGzipFile (OSError) si el magic no cuadra
            print(f"  ! ilegible, se salta: {fname} ({e})", file=sys.stderr)
            skipped += 1
            continue
        got = fetched_at_from(day, fname)
        if fname.endswith("_info.json.gz"):
            insert_stations(cur, feed)
            continue
        inserted += insert_status(cur, feed, fetched_at=got)
        # Filas ya presentes (insertadas por collect.py antes de existir la columna):
        # el DO NOTHING no las toca, así que la hora de captura se rellena aparte.
        cur.execute(
            "UPDATE dbizi_measurement SET fetched_at = %s WHERE ts = %s AND fetched_at IS NULL",
            (got, parse_ts(feed["last_updated"])),
        )
        backfilled += cur.rowcount
    return inserted, backfilled, skipped


def main():
    if not os.path.isdir(RAW):
        sys.exit(f"no existe {RAW}")
    days = sys.argv[1:] or sorted(d for d in os.listdir(RAW) if d.isdigit())
    if not days:
        print("sin días que procesar")
        return
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    tot_i = tot_b = tot_s = 0
    for day in days:
        ins, back, skip = process_day(cur, day)
        conn.commit()
        tot_i, tot_b, tot_s = tot_i + ins, tot_b + back, tot_s + skip
        print(f"{day}: {ins} filas intentadas, {back} fetched_at rellenados"
              + (f", {skip} ficheros ilegibles" if skip else ""), flush=True)
    conn.close()
    print(f"total: {tot_i} filas, {tot_b} fetched_at, {tot_s} ilegibles")


if __name__ == "__main__":
    main()
