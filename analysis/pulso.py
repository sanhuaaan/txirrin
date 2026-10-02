"""Póster "El pulso de Donostia": 70 estaciones, su semana tipo como latido.

Cada celda: actividad (llegadas+salidas) por hora de la semana tipo, lunes a
domingo, normalizada por estación (forma, no volumen). Orden oeste → este.
Arriba, el latido de la red entera.

Entrada: data/events.csv.gz + data/profiles.csv
Salida:  analysis/pulso.png

    python3 analysis/pulso.py
"""
import re

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BG, INK, MUT, ACC, HERO = "#0c1116", "#e8eef4", "#5d6b78", "#7fd4ff", "#e6a23c"

ev = pd.read_csv("data/events.csv.gz", parse_dates=["ts"])
ev["ts"] = ev.ts.dt.tz_convert("Europe/Madrid")
ev["slot"] = ev.ts.dt.dayofweek * 24 + ev.ts.dt.hour
ev["act"] = ev.arr + ev.dep
ndays = ev.groupby(ev.ts.dt.dayofweek).ts.apply(lambda s: s.dt.date.nunique())
st = pd.read_csv("data/profiles.csv").groupby("station_id")[["name", "lat", "lon"]].first()

pulse = ev.pivot_table(index="station_id", columns="slot", values="act", aggfunc="sum").reindex(columns=range(168)).fillna(0)
pulse = pulse / ndays.reindex(np.arange(168) // 24).to_numpy()      # media por hora de la semana tipo
tot = pulse.sum(1) / 2                                               # ~viajes/día (act/2)
sm = pulse.rolling(3, axis=1, center=True, min_periods=1).mean()
order = st.loc[sm.index].sort_values("lon").index                    # oeste -> este

NC, NR = 7, 10
fig = plt.figure(figsize=(13.5, 19), facecolor=BG)
gs = fig.add_gridspec(NR + 2, NC, left=.045, right=.965, top=.925, bottom=.035,
                      hspace=.95, wspace=.18, height_ratios=[2.2, .12] + [1] * NR)

fig.text(.045, .978, "EL PULSO DE DONOSTIA", color=INK, fontsize=34, fontweight="bold",
         family="monospace", ha="left", va="top")
fig.text(.045, .952, "la semana tipo de las 70 estaciones de Dbizi · medida cada 2 minutos durante 6 semanas · ordenadas de oeste a este",
         color=MUT, fontsize=11.5, ha="left", va="top")

# --- héroe: el latido de la red ---
ax = fig.add_subplot(gs[0, :], facecolor=BG)
net = sm.sum(0).to_numpy()
x = np.arange(168)
ax.fill_between(x, 0, net, color=HERO, alpha=.25, lw=0)
ax.plot(x, net, color=HERO, lw=1.8)
for d in range(7):
    if d >= 5:
        ax.axvspan(d * 24, (d + 1) * 24, ymax=.88, color=INK, alpha=.04, lw=0)
    ax.text(d * 24 + 12, -net.max() * .10, "LMXJVSD"[d], color=MUT, fontsize=11,
            ha="center", family="monospace")
ax.set_xlim(0, 167); ax.set_ylim(-net.max() * .16, net.max() * 1.06)
ax.axis("off")
ax.text(167, net.max() * 1.0, "toda la red, movimientos/hora", color=MUT, fontsize=9.5, ha="right")

# --- 70 latidos ---
for k, sid in enumerate(order):
    r, c = divmod(k, NC)
    axc = fig.add_subplot(gs[r + 2, c], facecolor=BG)
    y = sm.loc[sid].to_numpy()
    y = y / (y.max() or 1)
    axc.fill_between(x, 0, y, color=ACC, alpha=.22, lw=0)
    axc.plot(x, y, color=ACC, lw=.9)
    axc.axvspan(120, 168, ymax=.87, color=INK, alpha=.06, lw=0)
    axc.set_xlim(0, 167); axc.set_ylim(0, 1.15); axc.axis("off")
    nm = re.sub(r"^\s*\d+\s*[-–]*\s*", "", st.loc[sid, "name"])
    if "-" in nm and len(nm) > 17:               # "TOLOSA HIRIB.-IRAKASLE..." -> el tramo propio
        nm = nm.rsplit("-", 1)[-1]
    nm = nm.split("/")[0].strip().title()[:16]
    axc.text(0, 1.38, nm, color=INK, fontsize=8, ha="left", va="top", family="monospace")
    axc.text(167, 1.38, f"{tot[sid]:.0f}/día", color=MUT, fontsize=7, ha="right", va="top", family="monospace")

fig.text(.045, .012, "cada curva: llegadas + salidas por hora, de lunes a domingo (franja clara: fin de semana) · forma normalizada por estación",
         color=MUT, fontsize=9, ha="left")
fig.text(.965, .012, "txirrin · datos GBFS de Dbizi · ago-oct 2026", color=MUT, fontsize=9, ha="right")
fig.savefig("analysis/pulso.png", dpi=130, facecolor=BG)
print("analysis/pulso.png")
