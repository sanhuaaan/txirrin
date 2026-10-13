#!/usr/bin/env python3
"""Genera rates.json: la marea de cada estación para el reparto en el navegador.

Entrada: CSV station_id,wd,hour,day,dep,arr,p_empty,p_full,stock (publish_plan.sh;
         wd = lun…dom o fes para los festivos)
         + CSV station_id,capacity,lat,lon
         + CSV id,kind,starts_at,ends_at,lat,lon de los eventos de la ventana (tabla event).
Salida: por día de la semana y estación, 18 horas (6-23) de tasa de salidas y de
llegadas corregidas de censura (solo horas con la estación <80 % vacía/llena;
la conservación reparte las salidas recuperadas entre las llegadas de esa
hora) y el stock típico. Mismo método que analysis/reparto.py, con tres cosas
más (segunda vuelta, 2026-10-13):

- DÍA DE LA SEMANA, no tres tipos. El martes de Andoain kalea, el juevintxo de
  Gros o el +20 % del viernes se diluían en "laborable". Con ~8 semanas hay ~8
  días por casilla, poco: cada día de la semana se encoge hacia la media de su
  tipo (lab/sab/dom) como si tuviera K=3 días más de ella. Donde el día de la
  semana es consistente, se nota; donde es ruido, pesa la base. Los festivos
  ('fes') encogen hacia el domingo. Las claves lab/sab/dom se siguen dando
  (el simulador "Un día con reparto" las usa).
- SIN LAS HORAS DE EVENTO. Un partido metía su marea en la media de ese día y
  hora para todas las semanas. Las horas de [inicio-2 h, fin+1,5 h] se quitan
  de las medias para las estaciones a menos de 1.600 m del recinto (fútbol,
  baloncesto) o de toda la red (regata, carrera, ciclismo).
- PERFIL DE EVENTO: con esas mismas horas se mide el exceso de llegadas y
  salidas por estación y hora respecto a la base, por anillo (<800 m,
  800-1.600 m) y hora relativa al comienzo (-2 … +3). El navegador lo suma a
  la marea del día cuando hay evento. Medido en analysis/partidos.md.
"""
import csv
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

CENSOR, H0, H1 = 0.8, 6, 24
K = 3                                             # días "prestados" de la base al encoger
TIPO = {"lun": "lab", "mar": "lab", "mie": "lab", "jue": "lab", "vie": "lab", "sab": "sab", "dom": "dom", "fes": "dom"}
RINGS = (800, 1600)                               # m: anillos del perfil de evento
CITYWIDE = {"regata", "carrera", "ciclismo"}      # el evento es la ciudad entera
ANTES, DESPUES = 2.0, 1.5                         # h que se excluyen antes del inicio y tras el fin
OFFS = (-2, -1, 0, 1, 2, 3)                       # horas relativas al inicio para el perfil
TZ = ZoneInfo("Europe/Madrid")
M_DEG = 111320.0
src, caps, evs, out = sys.argv[1:5]

cap, pos = {}, {}
for r in csv.reader(open(caps)):
    if len(r) >= 2 and r[0].strip() and r[1].strip():
        cap[r[0]] = int(r[1])
        if len(r) >= 4 and r[2] and r[3]: pos[r[0]] = (float(r[2]), float(r[3]))

def dist(a, b):
    kx = M_DEG * math.cos(math.radians(a[0]))
    return math.hypot((a[1] - b[1]) * kx, (a[0] - b[0]) * M_DEG)

# eventos: horas excluidas por estación y día, y ventana del perfil
events = []
for r in csv.reader(open(evs)):
    if len(r) < 6 or not r[2].strip(): continue
    s = datetime.fromisoformat(r[2]).replace(tzinfo=timezone.utc).astimezone(TZ)
    e = datetime.fromisoformat(r[3]).replace(tzinfo=timezone.utc).astimezone(TZ)
    v = (float(r[4]), float(r[5])); kind = r[1]
    ring = {sid: (0 if d <= RINGS[0] else 1) for sid, p in pos.items() if (d := dist(p, v)) <= RINGS[1]}
    hours = set()                                 # (fecha, hora) que toca el evento, con margen
    t = s - timedelta(hours=ANTES)
    while t < e + timedelta(hours=DESPUES):
        hours.add((t.strftime("%Y-%m-%d"), t.hour)); t += timedelta(hours=1)
    events.append(dict(kind=kind, s=s, ring=ring, hours=hours, day=s.strftime("%Y-%m-%d")))
excluded = defaultdict(set)                       # sid -> {(day, hour)}
for ev in events:
    for sid in (pos if ev["kind"] in CITYWIDE else ev["ring"]):
        excluded[sid] |= ev["hours"]

# filas crudas por (sid, wd, h): limpias para las medias, todas para el perfil
acc = defaultdict(lambda: {"dep": [], "arr": [], "dep_all": [], "arr_all": [], "stock": [], "days": set()})
raw = {}                                          # (sid, day, hour) -> (dep, arr) sin corregir
n_excl = 0
for sid, wd, h, day, dep, arr, pe, pf, stock in csv.reader(open(src)):
    h, dep, arr, pe, pf = int(h), float(dep), float(arr), float(pe), float(pf)
    if not H0 <= h < H1: continue
    raw[(sid, day, h)] = (dep, arr, wd)
    if (day, h) in excluded.get(sid, ()): n_excl += 1; continue
    for key in ((sid, wd, h), (sid, TIPO.get(wd, wd), h)):
        a = acc[key]
        a["dep_all"].append(dep); a["arr_all"].append(arr); a["stock"].append(float(stock)); a["days"].add(day)
        if pe < CENSOR: a["dep"].append(dep / (1 - pe))
        if pf < CENSOR: a["arr"].append(arr / (1 - pf))
mean = lambda v: sum(v) / len(v) if v else 0.0
def tasa(a, k):
    return mean(a[k]) if a[k] else mean(a[k + "_all"])

rates = {}
blank = lambda: {"dep": [0.0] * (H1 - H0), "arr": [0.0] * (H1 - H0), "stock": [0.0] * (H1 - H0), "days": 0, "wdays": 0}
for (sid, key, h), a in acc.items():
    if key in TIPO:                               # día de la semana: encoger hacia la base de su tipo
        b = acc.get((sid, TIPO[key], h)); n = len(a["days"])
        if b is None: continue
        r = rates.setdefault(key, {}).setdefault(sid, blank())
        for k in ("dep", "arr"):
            r[k][h - H0] = (n * tasa(a, k) + K * tasa(b, k)) / (n + K)
        r["stock"][h - H0] = (n * mean(a["stock"]) + K * mean(b["stock"])) / (n + K)
        r["days"] = max(r["days"], len(b["days"]))   # lo que sostiene la casilla es la base
        r["wdays"] = max(r["wdays"], n)
    else:                                         # base por tipo de día, como antes
        r = rates.setdefault(key, {}).setdefault(sid, blank())
        r["dep"][h - H0] = tasa(a, "dep"); r["arr"][h - H0] = tasa(a, "arr")
        r["stock"][h - H0] = mean(a["stock"]); r["days"] = r["wdays"] = max(r["days"], len(a["days"]))
for dt, sts in rates.items():                     # conservación por hora: salidas == llegadas
    for i in range(H1 - H0):
        sd, sa = sum(r["dep"][i] for r in sts.values()), sum(r["arr"][i] for r in sts.values())
        k = sd / sa if sa > 0 else 1.0
        for r in sts.values(): r["arr"][i] *= k
    for r in sts.values():
        for key in ("dep", "arr", "stock"): r[key] = [round(v, 2) for v in r[key]]

# perfil de evento: exceso por estación y hora sobre la base de su tipo de día, por anillo
prof = {}
for kind in {ev["kind"] for ev in events}:
    evk = [ev for ev in events if ev["kind"] == kind]
    ex = {o: {0: {"dep": [], "arr": []}, 1: {"dep": [], "arr": []}} for o in OFFS}
    for ev in evk:
        for sid, ring in ev["ring"].items():
            for o in OFFS:
                t = ev["s"].replace(minute=0, second=0, microsecond=0) + timedelta(hours=o)
                row = raw.get((sid, t.strftime("%Y-%m-%d"), t.hour))
                if row is None or not H0 <= t.hour < H1: continue
                base = rates.get(TIPO.get(row[2], row[2]), {}).get(sid)
                if not base: continue
                ex[o][ring]["dep"].append(row[0] - base["dep"][t.hour - H0])
                ex[o][ring]["arr"].append(row[1] - base["arr"][t.hour - H0])
    prof[kind] = {"n": len(evk), "rings": list(RINGS), "offs": list(OFFS),
                  "dep": [[round(mean(ex[o][rg]["dep"]), 2) for o in OFFS] for rg in (0, 1)],
                  "arr": [[round(mean(ex[o][rg]["arr"]), 2) for o in OFFS] for rg in (0, 1)]}

json.dump({"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "h0": H0, "k": K,
           "cap": cap, "rates": rates, "events": prof}, open(out, "w"), separators=(",", ":"))
print(f"{out}: " + ", ".join(f"{dt} {len(s)}" for dt, s in sorted(rates.items())) +
      f"; {n_excl} horas-estación de evento fuera de las medias; perfiles: " +
      ", ".join(f"{k} n={v['n']}" for k, v in prof.items()))
