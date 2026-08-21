#!/usr/bin/env python3
"""Carga el histórico 10-min de Euskalmet (XML mensuales por estación) en Postgres.

Uso: DBIZI_DSN=... ./load_weather.py [año_inicio [año_fin]]  (por defecto 2026..año actual)
Decisión 2026-08-21: solo desde 2026 — la meteo acompaña al histórico de bicis (ago-2026);
más años no aportan y las cargas largas ahogaban la e2-micro. Ampliar hacia atrás cuando
haga falta es re-ejecutar con otro año de inicio.
Idempotente (ON CONFLICT DO NOTHING): un cron mensual re-carga el año en curso.
Descarga los XML individuales del portal (no hace falta el zip anual completo).
"""
import os
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import psycopg2

DSN = os.environ["DBIZI_DSN"]
BASE = ("https://opendata.euskadi.eus/contenidos/ds_meteorologicos/"
        "met_stations_ds_{y}/opendata/{y}/{st}/{st}_{y}_{m}.xml")

INTERVAL_MIN = 10  # paso de la serie oficial (verificado: 144 lecturas/día)

STATIONS = {  # id: (nombre, lat, lon) — añadir C007 Santa Clara si algún día hace falta viento de costa
    "C017": ("Miramon", 43.2868, -1.97121),
}

FIELDS = {  # prefijo del tag XML (sin la altura del sensor) -> columna
    "Tem.Aire.": "temperature",
    "Precip..": "precipitation",
    "Humedad.": "humidity",
    "Vel.Med.": "wind_speed",
    "Vel.Max.": "wind_max",
    "Dir.Med.": "wind_dir",
    "Irradia..": "irradiance",
}
COLS = list(FIELDS.values())


def field_col(tag):
    for pref, col in FIELDS.items():
        if tag.startswith(pref):
            return col
    return None


def load_month(cur, st, y, m):
    url = BASE.format(y=y, m=m, st=st)
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            xml = r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return 0  # mes/estación sin datos (p.ej. antes del alta de la estación)
        raise
    rows = 0
    for dia in ET.fromstring(xml):
        yy, mm, dd = (int(x) for x in dia.attrib["Dia"].split("-"))
        for hora in dia:
            hh, mi = (int(x) for x in hora.attrib["Hora"].split(":"))
            ts = datetime(yy, mm, dd, hh, mi, tzinfo=timezone.utc)
            vals = dict.fromkeys(COLS)
            for meteoros in hora:
                for el in meteoros:
                    col = field_col(el.tag)
                    if col and el.text:
                        try:
                            vals[col] = float(el.text)
                        except ValueError:
                            pass
            cur.execute(
                f"""INSERT INTO weather_measurement
                        (station_id, ts, interval_minutes, {', '.join(COLS)})
                    VALUES (%s, %s, %s, {', '.join(['%s'] * len(COLS))})
                    ON CONFLICT DO NOTHING""",
                [st, ts, INTERVAL_MIN] + [vals[c] for c in COLS],
            )
            rows += 1
    return rows


def main():
    y0 = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    y1 = int(sys.argv[2]) if len(sys.argv) > 2 else datetime.now(timezone.utc).year
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    for st, (name, lat, lon) in STATIONS.items():
        cur.execute(
            """INSERT INTO weather_station (station_id, name, geom)
               VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
               ON CONFLICT (station_id) DO NOTHING""",
            (st, name, lon, lat),
        )
        for y in range(y0, y1 + 1):
            n = sum(load_month(cur, st, y, m) for m in range(1, 13))
            conn.commit()
            print(f"{st} {y}: {n} lecturas", flush=True)


if __name__ == "__main__":
    main()
