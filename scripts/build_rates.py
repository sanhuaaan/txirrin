#!/usr/bin/env python3
"""Genera rates.json: la marea de cada estación para el reparto en el navegador.

Entrada: CSV station_id,dt,hour,day,dep,arr,p_empty,p_full,stock (publish_plan.sh)
         + CSV station_id,capacity.
Salida: por tipo de día y estación, 18 horas (6-23) de tasa de salidas y de
llegadas corregidas de censura (solo horas con la estación <80 % vacía/llena;
la conservación reparte las salidas recuperadas entre las llegadas de esa
hora) y el stock típico. Mismo método que analysis/reparto.py.
"""
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone

CENSOR, H0, H1 = 0.8, 6, 24
src, caps, out = sys.argv[1:4]
acc = defaultdict(lambda: {"dep": [], "arr": [], "dep_all": [], "arr_all": [], "stock": [], "days": set()})
for sid, dt, h, day, dep, arr, pe, pf, stock in csv.reader(open(src)):
    h, dep, arr, pe, pf = int(h), float(dep), float(arr), float(pe), float(pf)
    if not H0 <= h < H1:
        continue
    a = acc[(sid, dt, h)]
    a["dep_all"].append(dep); a["arr_all"].append(arr); a["stock"].append(float(stock)); a["days"].add(day)
    if pe < CENSOR: a["dep"].append(dep / (1 - pe))
    if pf < CENSOR: a["arr"].append(arr / (1 - pf))
mean = lambda v: sum(v) / len(v) if v else 0.0
rates = {}
for (sid, dt, h), a in acc.items():
    r = rates.setdefault(dt, {}).setdefault(sid, {"dep": [0.0] * (H1 - H0), "arr": [0.0] * (H1 - H0),
                                                  "stock": [0.0] * (H1 - H0), "days": 0})
    r["dep"][h - H0] = mean(a["dep"]) if a["dep"] else mean(a["dep_all"])
    r["arr"][h - H0] = mean(a["arr"]) if a["arr"] else mean(a["arr_all"])
    r["stock"][h - H0] = mean(a["stock"])
    r["days"] = max(r["days"], len(a["days"]))
for dt, sts in rates.items():                    # conservación por hora: salidas == llegadas
    for i in range(H1 - H0):
        sd, sa = sum(r["dep"][i] for r in sts.values()), sum(r["arr"][i] for r in sts.values())
        k = sd / sa if sa > 0 else 1.0
        for r in sts.values(): r["arr"][i] *= k
    for r in sts.values():
        for key in ("dep", "arr", "stock"): r[key] = [round(v, 2) for v in r[key]]
cap = {sid: int(c) for sid, c in csv.reader(open(caps)) if sid.strip()}
json.dump({"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "h0": H0,
           "cap": cap, "rates": rates}, open(out, "w"), separators=(",", ":"))
print(f"{out}: " + ", ".join(f"{dt} {len(s)} estaciones" for dt, s in rates.items()))
