#!/usr/bin/env python3
"""Meteo reciente vía Open-Meteo (sin key, uso no comercial): tapa el hueco de ~2 meses
que Open Data Euskadi tarda en publicar los XML oficiales de Miramón.

Reanálisis horario sobre la malla del punto de Miramón, guardado como estación
'OPENMETEO' (serie separada de C017; el análisis prefiere C017 donde exista).
Últimos 7 días en cada ejecución; DO UPDATE porque el modelo revisa valores recientes.
Cron diario en la VM.
"""
import json
import os
import urllib.request
from datetime import datetime, timezone

import psycopg2

DSN = os.environ["DBIZI_DSN"]
URL = ("https://api.open-meteo.com/v1/forecast?latitude=43.2868&longitude=-1.97121"
       "&past_days=7&forecast_days=1&wind_speed_unit=ms&timezone=UTC"
       "&hourly=temperature_2m,precipitation,relative_humidity_2m,"
       "wind_speed_10m,wind_gusts_10m,wind_direction_10m")


def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "dbizi-weather"})
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
                 (station_id, ts, temperature, precipitation, humidity,
                  wind_speed, wind_max, wind_dir)
               VALUES ('OPENMETEO', %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (station_id, ts) DO UPDATE
                 SET temperature = EXCLUDED.temperature,
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
