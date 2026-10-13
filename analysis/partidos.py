#!/usr/bin/env python3
"""¿Cuánto mueve un partido en Anoeta? Medido en las estaciones de alrededor.

Hasta ahora sabíamos dónde y cuándo había partido (tabla `event`) y el mapa
lo marcaba, pero el reparto óptimo trabajaba con la media del tipo de día,
partidos incluidos y sin saber que lo eran. Antes de meter una "capa de
evento" en el modelo hay que saber si el efecto existe y cuánto vale.

Método: para las estaciones a menos de RADIO m del recinto, salidas y
llegadas por tramos de 15 min alrededor del saque (-150 … +210 min), en cada
partido, frente a la línea base: las mismas estaciones, el mismo día de la
semana y la misma hora del reloj en los días sin partido ni festivo (media y
desviación). El exceso es partido − base. Lo mismo para el baloncesto en
Illumbe y las regatas de la Concha, con lo que haya.

Entrada: data/events.csv.gz (salidas/llegadas por captura), data/eventos_contexto.csv
(eventos, festivos y estaciones con coordenadas, volcados de la base).
Salida: analysis/partidos.md y analysis/partidos.png.
"""
import csv, gzip, math, statistics as st
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Madrid"); UTC = timezone.utc
RADIO, BIN = 800, 15                       # m alrededor del recinto; minutos por tramo
T0, T1 = -150, 210                         # minutos respecto al saque
M_DEG = 111320.0

events, holidays, stations = [], set(), {}
for r in csv.reader(open("data/eventos_contexto.csv", encoding="utf-8")):
    if not r: continue
    if r[0] == "E":
        events.append(dict(id=r[1], kind=r[2], s=datetime.fromisoformat(r[3]).replace(tzinfo=UTC),
                           e=datetime.fromisoformat(r[4]).replace(tzinfo=UTC), lat=float(r[5]), lon=float(r[6]), name=r[7]))
    elif r[0] == "H": holidays.add(r[1])
    elif r[0] == "S": stations[r[1]] = dict(lat=float(r[2]), lon=float(r[3]), name=r[5])

def dist(a, b):
    kx = M_DEG * math.cos(math.radians(a["lat"]))
    return math.hypot((a["lon"] - b["lon"]) * kx, (a["lat"] - b["lat"]) * M_DEG)

# salidas/llegadas por estación, día local, minuto del día (resolución de captura)
flow = defaultdict(lambda: defaultdict(lambda: [0, 0]))     # (sid) -> (fecha, minuto) -> [dep, arr]
days_seen = set()
with gzip.open("data/events.csv.gz", "rt", encoding="utf-8") as f:
    rd = csv.reader(f); next(rd)
    for sid, ts, dep, arr in rd:
        t = datetime.fromisoformat(ts.replace("+00", "+00:00")).astimezone(TZ)
        key = (t.date(), t.hour * 60 + t.minute)
        c = flow[sid][key]; c[0] += int(dep); c[1] += int(arr)
        days_seen.add(t.date())
days_seen = sorted(days_seen)
event_days = {ev["s"].astimezone(TZ).date() for ev in events}

def bins_for(ids, day, kick_min):
    """Salidas y llegadas de `ids` el día `day`, por tramos de BIN min respecto a kick_min."""
    nb = (T1 - T0) // BIN
    dep, arr = [0] * nb, [0] * nb
    for sid in ids:
        for (d, m), (x, y) in flow[sid].items():
            if d != day: continue
            k = (m - kick_min - T0) // BIN
            if 0 <= k < nb: dep[k] += x; arr[k] += y
    return dep, arr

def analyse(ev, radius=RADIO):
    venue = dict(lat=ev["lat"], lon=ev["lon"])
    ids = [sid for sid, s in stations.items() if dist(s, venue) <= radius]
    s_loc = ev["s"].astimezone(TZ); day = s_loc.date(); kick = s_loc.hour * 60 + s_loc.minute
    dur = int((ev["e"] - ev["s"]).total_seconds() // 60)
    dep, arr = bins_for(ids, day, kick)
    # base: mismo día de la semana, sin evento ni festivo; si hay menos de 4, mismo tipo (lab / sab / dom)
    same = [d for d in days_seen if d.weekday() == day.weekday() and d not in event_days and str(d) not in holidays and d != day]
    if len(same) < 4:
        tipo = lambda d: 0 if d.weekday() < 5 else 1 if d.weekday() == 5 else 2
        same = [d for d in days_seen if tipo(d) == tipo(day) and d not in event_days and str(d) not in holidays and d != day]
    base = [bins_for(ids, d, kick) for d in same]
    nb = len(dep)
    mdep = [st.mean(b[0][k] for b in base) for k in range(nb)]
    marr = [st.mean(b[1][k] for b in base) for k in range(nb)]
    sdep = [st.pstdev([b[0][k] for b in base]) for k in range(nb)]
    sarr = [st.pstdev([b[1][k] for b in base]) for k in range(nb)]
    return dict(ev=ev, ids=ids, day=day, kick=kick, dur=dur, dep=dep, arr=arr, mdep=mdep, marr=marr,
                sdep=sdep, sarr=sarr, nbase=len(same))

def window(res, a, b, what):
    """Suma de exceso (y de base) en los tramos cuyo inicio cae en [a, b) min respecto al saque."""
    tot = basev = 0.0
    for k in range(len(res["dep"])):
        t = T0 + k * BIN
        if a <= t < b:
            tot += res[what][k]; basev += res["m" + what][k]
    return tot, basev

out = ["# ¿Cuánto mueve un partido? (estaciones a menos de %d m del recinto)\n" % RADIO,
       "Exceso = lo que hubo el día del evento − la media de las mismas estaciones, el mismo día de la semana y la misma hora, en los días sin evento. Entre paréntesis, la base. «Antes» es el tramo de 2 h previo al comienzo (hasta +15 min); «después», de 15 min antes del final a 1 h 15 después.\n"]
rows, series = [], defaultdict(list)
for ev in events:
    if ev["s"].astimezone(TZ).date() not in days_seen: continue
    res = analyse(ev)
    s_loc = ev["s"].astimezone(TZ)
    a_arr, a_base = window(res, -120, 15, "arr")
    d_dep, d_base = window(res, res["dur"] - 15, res["dur"] + 75, "dep")
    rows.append((ev, res, a_arr, a_base, d_dep, d_base))
    series[ev["kind"]].append(res)
    out.append(f"- **{ev['name']}** · {s_loc:%a %d/%m %H:%M} · {len(res['ids'])} estaciones, base de {res['nbase']} días: "
               f"llegadas antes **{a_arr - a_base:+.0f}** ({a_base:.0f}); salidas después **{d_dep - d_base:+.0f}** ({d_base:.0f}).")

def resumen(kind, label):
    rs = series.get(kind, [])
    if not rs: return
    n = len(rs)
    ex_arr = [window(r, -120, 15, "arr") for r in rs]; ex_dep = [window(r, r["dur"] - 15, r["dur"] + 75, "dep") for r in rs]
    da = [a - b for a, b in ex_arr]; dd = [a - b for a, b in ex_dep]
    out.append(f"\n## {label}: {n} evento{'s' if n > 1 else ''}\n")
    out.append(f"- Llegadas en las 2 h previas: exceso medio **{st.mean(da):+.1f}** bicis por evento "
               f"(mín {min(da):+.0f}, máx {max(da):+.0f}) sobre una base de {st.mean(b for _, b in ex_arr):.1f}.")
    out.append(f"- Salidas en la hora y media del final: exceso medio **{st.mean(dd):+.1f}** "
               f"(mín {min(dd):+.0f}, máx {max(dd):+.0f}) sobre una base de {st.mean(b for _, b in ex_dep):.1f}.")
    # perfil por tramo: exceso medio por partido, en bicis por tramo de 15 min
    nb = len(rs[0]["dep"])
    prof_arr = [st.mean(r["arr"][k] - r["marr"][k] for r in rs) for k in range(nb)]
    prof_dep = [st.mean(r["dep"][k] - r["mdep"][k] for r in rs) for k in range(nb)]
    out.append("\n| min desde el saque | exceso llegadas | exceso salidas |\n|---|---|---|")
    for k in range(nb):
        t = T0 + k * BIN
        if t % 30 == 0: out.append(f"| {t:+d} | {prof_arr[k] + (prof_arr[k+1] if k+1 < nb else 0):+.1f} | {prof_dep[k] + (prof_dep[k+1] if k+1 < nb else 0):+.1f} |")
    return prof_arr, prof_dep

# anillos de distancia, solo fútbol
def anillos():
    fut = [ev for ev in events if ev["kind"] == "futbol" and ev["s"].astimezone(TZ).date() in days_seen]
    out.append("\n## Fútbol por anillo de distancia (exceso medio por partido)\n\n| anillo | estaciones | llegadas antes | salidas después |\n|---|---|---|---|")
    venue = dict(lat=fut[0]["lat"], lon=fut[0]["lon"])
    prev = 0
    for rad in (400, 800, 1200, 1600):
        ids_in = {sid for sid, s in stations.items() if prev < dist(s, venue) <= rad}
        if not ids_in: prev = rad; continue
        da, dd = [], []
        for ev in fut:
            r = analyse(ev, rad); r2 = analyse(ev, prev) if prev else None
            a, b = window(r, -120, 15, "arr"); d, e = window(r, r["dur"] - 15, r["dur"] + 75, "dep")
            if r2:
                a2, b2 = window(r2, -120, 15, "arr"); d2, e2 = window(r2, r2["dur"] - 15, r2["dur"] + 75, "dep")
                a, b, d, e = a - a2, b - b2, d - d2, e - e2
            da.append(a - b); dd.append(d - e)
        out.append(f"| {prev}–{rad} m | {len(ids_in)} | {st.mean(da):+.1f} | {st.mean(dd):+.1f} |")
        prev = rad

prof = resumen("futbol", "Fútbol en Anoeta")
resumen("baloncesto", "Baloncesto en Illumbe")
resumen("regata", "Regatas de la Concha")
anillos()
fut_near = [sid for sid, s in stations.items() if dist(s, dict(lat=43.3014, lon=-1.9735)) <= RADIO]
out.append("\nEstaciones a menos de %d m de Anoeta: " % RADIO + ", ".join(stations[s]["name"] for s in sorted(fut_near, key=int)) + ".")
open("analysis/partidos.md", "w", encoding="utf-8").write("\n".join(out) + "\n")

if prof:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    nb = len(prof[0]); t = [T0 + k * BIN for k in range(nb)]
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.bar([x - 3 for x in t], prof[0], width=6, label="llegadas (exceso)", color="#3987e5")
    ax.bar([x + 3 for x in t], [-v for v in prof[1]], width=6, label="salidas (exceso, hacia abajo)", color="#e66767")
    ax.axvline(0, color="#999", lw=1); ax.axvline(105, color="#999", lw=1, ls="--")
    ax.set_xlabel("minutos desde el saque (línea discontinua: final aproximado)"); ax.set_ylabel("bicis por tramo de 15 min")
    ax.set_title("Fútbol en Anoeta: exceso medio por partido en las estaciones a <%d m (%d partidos)" % (RADIO, len(series["futbol"])))
    ax.legend(loc="upper left"); fig.tight_layout(); fig.savefig("analysis/partidos.png", dpi=110)
print(open("analysis/partidos.md", encoding="utf-8").read())
