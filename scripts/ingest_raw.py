#!/usr/bin/env python3
"""Reingesta el crudo a Postgres, desde ~/raw/YYYYMMDD/*.json.gz o desde los
~/raw/YYYYMMDD.tar.xz que sube raw_upload.sh al bucket (para restaurar: bajar
los tars a ~/raw y ejecutar esto). Los .bad (crudo que no validó) se saltan.

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
import tarfile
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


def snapshots(day):
    """Itera (nombre, json) de un día, venga en directorio o en tar.gz.
    El directorio manda si existe (es lo más reciente)."""
    day_dir = os.path.join(RAW, day)
    tar_path = next((p for p in (os.path.join(RAW, day + ext) for ext in (".tar.xz", ".tar.gz")) if os.path.isfile(p)), None)
    if os.path.isdir(day_dir):
        for fname in sorted(os.listdir(day_dir)):
            if fname.endswith(".json.gz"):
                yield fname, lambda p=os.path.join(day_dir, fname): read_gz(p)
    elif tar_path:
        with tarfile.open(tar_path, "r:*") as tar:
            for m in sorted(tar.getmembers(), key=lambda m: m.name):
                if m.isfile() and m.name.endswith(".json"):
                    yield os.path.basename(m.name) + ".gz", lambda m=m, t=tar: json.loads(t.extractfile(m).read())


def process_day(cur, day):
    inserted = backfilled = skipped = 0
    for fname, read in snapshots(day):
        if ".bad." in fname:
            continue                                  # el feed no validó: no hay qué ingerir
        try:
            feed = read()
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
    days = sys.argv[1:] or sorted({d[:8] for d in os.listdir(RAW) if d[:8].isdigit() and (len(d) == 8 or ".tar." in d)})
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
