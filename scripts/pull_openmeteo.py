#!/usr/bin/env python3
"""Meteo reciente vía Open-Meteo (sin key, uso no comercial): tapa el hueco de ~2 meses
que Open Data Euskadi tarda en publicar los XML oficiales de Miramón.

OJO: serie HORARIA. precipitation son mm acumulados en 1 h, frente a los mm/10min de
C017 — por eso se guarda interval_minutes: sin él, los umbrales de lluvia no son
comparables entre las dos series (ver comentario en sql/schema.sql).

Reanálisis horario sobre la malla del punto de Miramón, guardado como estación
'OPENMETEO' (serie separada de C017; el análisis prefiere C017 donde exista).
DO UPDATE porque el modelo revisa valores recientes.

Uso:
  ./pull_openmeteo.py                        últimos 7 días (lo que hace el cron diario)
  ./pull_openmeteo.py 30                     últimos 30 días (máx. 92), tras una caída larga
  ./pull_openmeteo.py 2026-07-01 2026-08-21  rango exacto vía API de archivo

El rango existe para poder rehacer un hueco desde cero: la serie arranca en julio de
2026 y sin esto no era reproducible desde el repo. La API de archivo va ~2 días por
detrás del presente, así que para lo más reciente hay que usar la forma de días.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

import psycopg2

DSN = os.environ["DBIZI_DSN"]
PUNTO = "latitude=43.2868&longitude=-1.97121"
COMUN = ("&wind_speed_unit=ms&timezone=UTC"
         "&hourly=temperature_2m,precipitation,relative_humidity_2m,"
         "wind_speed_10m,wind_gusts_10m,wind_direction_10m")
FORECAST = f"https://api.open-meteo.com/v1/forecast?{PUNTO}&past_days={{d}}&forecast_days=1{COMUN}"
ARCHIVO = f"https://archive-api.open-meteo.com/v1/archive?{PUNTO}&start_date={{a}}&end_date={{b}}{COMUN}"
MAX_DIAS = 92  # tope documentado de past_days; por encima, usar el rango de fechas


def url_de(args):
    if not args:
        return FORECAST.format(d=7)
    if len(args) == 1:
        if not args[0].isdigit() or not 1 <= int(args[0]) <= MAX_DIAS:
            sys.exit(f"días debe ser un entero entre 1 y {MAX_DIAS}; "
                     "para ventanas mayores pasa un rango YYYY-MM-DD YYYY-MM-DD")
        return FORECAST.format(d=int(args[0]))
    if len(args) > 2:
        sys.exit("como mucho dos argumentos: días, o fecha_inicio fecha_fin")
    for a in args:
        try:
            datetime.strptime(a, "%Y-%m-%d")
        except ValueError:
            sys.exit(f"fecha no válida: {a} (formato YYYY-MM-DD)")
    if args[0] > args[1]:
        sys.exit("la fecha de inicio va después de la de fin")
    return ARCHIVO.format(a=args[0], b=args[1])


def main():
    req = urllib.request.Request(url_de(sys.argv[1:]), headers={"User-Agent": "dbizi-weather"})
    with urllib.request.urlopen(req, timeout=60) as r:
        h = json.load(r)["hourly"]

    now = datetime.now(timezone.utc)
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO weather_station (station_id, name, geom, source)
           VALUES ('OPENMETEO', 'Open-Meteo (malla Miramon)',
                   ST_SetSRID(ST_MakePoint(-1.97121, 43.2868), 4326), 'open-meteo')
           ON CONFLICT (station_id) DO NOTHING"""
    )
    rows = 0
    for i, t in enumerate(h["time"]):
        ts = datetime.fromisoformat(t).replace(tzinfo=timezone.utc)
        if ts > now:
            continue  # el tramo futuro es predicción, no observación
        cur.execute(
            """INSERT INTO weather_measurement
                 (station_id, ts, interval_minutes, temperature, precipitation,
                  humidity, wind_speed, wind_max, wind_dir)
               VALUES ('OPENMETEO', %s, 60, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (station_id, ts) DO UPDATE
                 SET interval_minutes = EXCLUDED.interval_minutes,
                     temperature = EXCLUDED.temperature,
                     precipitation = EXCLUDED.precipitation,
                     humidity = EXCLUDED.humidity,
                     wind_speed = EXCLUDED.wind_speed,
                     wind_max = EXCLUDED.wind_max,
                     wind_dir = EXCLUDED.wind_dir""",
            (ts, h["temperature_2m"][i], h["precipitation"][i],
             h["relative_humidity_2m"][i], h["wind_speed_10m"][i],
             h["wind_gusts_10m"][i], h["wind_direction_10m"][i]),
        )
        rows += 1
    conn.commit()
    print(f"{rows} horas actualizadas")


if __name__ == "__main__":
    main()
