#!/usr/bin/env python3
"""Backfill e ingesta incremental: historial git de dbizi-raw -> Postgres.

Re-ejecutable: hace git pull, procesa solo commits nuevos (estado en ~/.dbizi_backfill_last)
y usa ON CONFLICT DO NOTHING. Sirve como backfill inicial y como cron de ingesta.

Uso: DBIZI_DSN="host=localhost dbname=dbizi user=dbizi password=..." ./backfill.py
     DBIZI_RAW: ruta al clon de dbizi-raw (por defecto ~/dbizi-raw)
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

import psycopg2

REPO = os.environ.get("DBIZI_RAW", os.path.expanduser("~/dbizi-raw"))
STATE = os.path.expanduser("~/.dbizi_backfill_last")
DSN = os.environ["DBIZI_DSN"]

MECHANICAL = {"FIT", "ICONIC", "METRO"}
ELECTRIC = {"EFIT", "BOOST", "COSMO", "ASTRO", "CHLOE"}  # CHLOE = patinete eléctrico


def git(*args):
    return subprocess.run(("git", "-C", REPO) + args, capture_output=True, text=True, check=True).stdout


def parse_ts(v):
    if isinstance(v, (int, float)):  # GBFS v2 daba epoch en segundos
        return datetime.fromtimestamp(v, tz=timezone.utc)
    # PBSC recorta los ceros de la fracción ("...:56.33Z", "...:56.3Z") y fromisoformat
    # solo admite 3 o 6 dígitos antes de Python 3.11: reventaba el snapshot completo en
    # ~13% de las estaciones. La fracción de segundo no aporta nada muestreando cada 2 min.
    return datetime.fromisoformat(re.sub(r"\.\d+", "", str(v)).replace("Z", "+00:00"))


def station_name(st):
    n = st.get("name")
    if isinstance(n, list):  # GBFS v3: [{"text": ..., "language": ...}]
        for e in n:
            if str(e.get("language", "")).startswith("es"):
                return e["text"]
        return n[0]["text"] if n else st["station_id"]
    return n or st["station_id"]


def type_counts(st):
    vts = st.get("vehicle_types_available")
    if not vts:
        return None, None
    mech = elec = 0
    for v in vts:
        if "vehicle_type_id" in v:  # forma estándar v2.3/v3
            tid, c = v["vehicle_type_id"], v.get("count", 0)
        else:  # forma compacta {"FIT": 3} vista en PBSC
            tid, c = next(iter(v.items()))
        if tid in MECHANICAL:
            mech += c or 0
        elif tid in ELECTRIC:
            elec += c or 0
    return mech, elec


def insert_stations(cur, info):
    for st in info["data"]["stations"]:
        cur.execute(
            """INSERT INTO dbizi_station (station_id, name, geom, capacity, address, post_code)
               VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s)
               ON CONFLICT (station_id) DO UPDATE
                 SET name = EXCLUDED.name, geom = EXCLUDED.geom,
                     capacity = EXCLUDED.capacity, address = EXCLUDED.address,
                     post_code = EXCLUDED.post_code, updated_at = now()""",
            (st["station_id"], station_name(st), st["lon"], st["lat"],
             st.get("capacity"), st.get("address"), st.get("post_code")),
        )


def insert_status(cur, feed, fetched_at=None):
    """fetched_at = instante real de captura; None cuando no se conoce (historial git)."""
    ts = parse_ts(feed["last_updated"])
    rows = 0
    for st in feed["data"]["stations"]:
        mech, elec = type_counts(st)
        cur.execute(
            """INSERT INTO dbizi_measurement
                 (station_id, ts, fetched_at, bikes_available, docks_available,
                  mechanical_available, electric_available,
                  vehicles_disabled, docks_disabled, bikes_overflow,
                  is_installed, is_renting, is_returning, last_reported)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT DO NOTHING""",
            (st["station_id"], ts, fetched_at,
             st.get("num_vehicles_available", st.get("num_bikes_available")),
             st.get("num_docks_available"), mech, elec,
             st.get("num_vehicles_disabled"), st.get("num_docks_disabled"),
             st.get("num_bikes_overflow"),
             st.get("is_installed"), st.get("is_renting"), st.get("is_returning"),
             parse_ts(st["last_reported"]) if st.get("last_reported") else None),
        )
        rows += 1
    return rows


def load_stations(cur):
    insert_stations(cur, json.loads(git("show", "HEAD:station_information.json")))


def load_status(cur, commit):
    try:
        feed = json.loads(git("show", f"{commit}:station_status.json"))
    except subprocess.CalledProcessError:
        return 0  # commit sin station_status (p.ej. el inicial del workflow)
    return insert_status(cur, feed)


def main():
    try:
        git("pull", "-q")
    except subprocess.CalledProcessError:
        pass  # remoto retirado (2026-08-21): se trabaja solo con el clon local
    last = open(STATE).read().strip() if os.path.exists(STATE) else None
    commits = git("rev-list", "--reverse", f"{last}..HEAD" if last else "HEAD").split()
    if not commits:
        print("sin commits nuevos")
        return
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    load_stations(cur)
    total = sum(load_status(cur, c) for c in commits)
    conn.commit()
    with open(STATE, "w") as f:
        f.write(commits[-1])
    print(f"{len(commits)} snapshots procesados, {total} filas insertadas/intentadas")


if __name__ == "__main__":
    sys.exit(main())
