#!/usr/bin/env python3
"""Genera plan.json para el planificador de viajes del timelapse (solo stdlib).

Entrada (CSV de publish_plan.sh): station_id,daytype,hour,s_empty,s_full,s_noelec,days
con las SUMAS de las fracciones diarias, y la lista de festivos futuros.
Salida: por estación y tipo de día, 24 horas de [p_vacía, p_llena, p_sin_eléctricas]
en %, encogidas hacia la media de la red cuando hay pocos días.

Calibrado en analysis/plan_calibration.md: vacía y sin eléctricas, k=2 pseudo-días;
llena no gana a la media de red, así que k=10 (casi la media) y la web la muestra
solo cualitativa.
"""
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone

K = (2, 10, 2)                                   # pseudo-días: vacía, llena, sin eléctricas

src, hol, out = sys.argv[1:4]
rows = [r for r in csv.reader(open(src)) if len(r) == 7 and r[0].strip()]
net = defaultdict(lambda: [0.0, 0.0, 0.0, 0])    # (daytype, hour) -> sumas + días
for sid, dt, h, *s, d in rows:
    acc = net[(dt, int(h))]
    for i in range(3): acc[i] += float(s[i])
    acc[3] += int(d)

st = {}
for sid, dt, h, *s, d in rows:
    h, d = int(h), int(d)
    n = net[(dt, h)]
    p = [round(100 * (float(s[i]) + K[i] * n[i] / n[3]) / (d + K[i])) for i in range(3)]
    st.setdefault(sid, {}).setdefault(dt, [None] * 24)[h] = p
days = {}
for sid, dt, h, *s, d in rows:
    days[dt] = max(days.get(dt, 0), int(d))

json.dump({"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "days": days, "holidays": [r[0] for r in csv.reader(open(hol)) if r and r[0].strip()],
           "stations": st}, open(out, "w"), separators=(",", ":"))
print(f"{out}: {len(st)} estaciones, días por tipo {days}")
