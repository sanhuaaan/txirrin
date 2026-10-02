"""¿Saben las bicis qué día es el pintxo-pote de cada barrio?

Firma buscada: exceso recurrente de LLEGADAS en tarde de diario (19-23 h) en
las estaciones de una zona, siempre el mismo día de la semana. No existe
fuente estructurada del pintxo-pote: aquí se intenta detectar desde los datos
y que un nativo valide el mapa.

Entrada: data/events.csv.gz + data/profiles.csv
Salida:  analysis/pintxopote.png y markdown por stdout

    python3 analysis/pintxopote.py > analysis/pintxopote.md
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

H0, H1 = 19, 23                 # tarde de pintxo-pote: 19:00-22:59
MIN_ARR = 6                     # llegadas/tarde mínimas para opinar
MIN_RATIO = 1.3                 # exceso mínimo frente al resto de diarios
DOWS = ["lunes", "martes", "miércoles", "jueves", "viernes"]

ev = pd.read_csv("data/events.csv.gz", parse_dates=["ts"])
ev["ts"] = ev.ts.dt.tz_convert("Europe/Madrid")
ev = ev[(ev.ts.dt.hour >= H0) & (ev.ts.dt.hour < H1) & (ev.ts.dt.dayofweek < 5)]
ev["date"] = ev.ts.dt.date
ev["dow"] = ev.ts.dt.dayofweek
st = pd.read_csv("data/profiles.csv").groupby("station_id")[["name", "lat", "lon"]].first()

# llegadas por estación × tarde concreta, cuadrado con todas las tardes (0 si nada)
day = ev.groupby(["station_id", "date", "dow"]).arr.sum().reset_index()
dates = ev[["date", "dow"]].drop_duplicates()
full = (day.set_index(["station_id", "date"])
          .reindex(pd.MultiIndex.from_product([st.index, dates.date], names=["station_id", "date"]))
          .arr.fillna(0).reset_index().merge(dates, on="date"))

# el viernes la RED entera sube (~+20 %, arranque del finde): se deflacta cada
# día por su factor de red, y lo que quede es exceso LOCAL — la firma buscada
netf = full.groupby("dow").arr.mean()
netf = netf / netf.mean()

rows = []
for sid, g in full.groupby("station_id"):
    m = g.groupby("dow").arr.mean() / netf
    if len(m) < 5:
        continue
    for d in range(5):
        rest = m.drop(d).mean()
        if m[d] >= MIN_ARR and rest > 0 and m[d] / rest >= MIN_RATIO:
            # consistencia: ¿cuántas de las tardes de ese día superan la media del resto?
            hits = (g[g.dow == d].arr / netf[d] > rest).mean()
            rows.append((sid, d, m[d], rest, m[d] / rest, hits))
r = pd.DataFrame(rows, columns=["sid", "dow", "arr_d", "arr_resto", "ratio", "consistencia"])
r = r[r.consistencia >= 0.7]                   # el exceso tiene que repetirse, no ser una noche loca
best = r.sort_values("ratio", ascending=False).groupby("sid").head(1)

print(f"# ¿Detectan las bicis el pintxo-pote? (llegadas {H0}-{H1} h, lunes-viernes, "
      f"{dates.date.nunique()} tardes)\n")
print("Exceso LOCAL: llegadas del día, deflactadas por el factor de red de ese día "
      "(el viernes sube en todas partes y eso no es pintxo-pote), frente al resto de "
      "diarios; se exige repetirse en >=70 % de las semanas.\n")
print("| estación | día | llegadas esa tarde | resto de tardes | exceso | semanas que se repite |")
print("|---|---|---|---|---|---|")
for _, x in best.sort_values("ratio", ascending=False).head(18).iterrows():
    print(f"| {st.loc[x.sid,'name']} | **{DOWS[int(x.dow)]}** | {x.arr_d:.0f} | {x.arr_resto:.0f} "
          f"| ×{x.ratio:.1f} | {x.consistencia*100:.0f} % |")

net = full.merge(dates, on="date", suffixes=("", "_"))  # red entera por dow
nm = full.groupby("dow").arr.mean()
print("\nRed entera (media de llegadas por estación y tarde): " +
      ", ".join(f"{DOWS[d]} {nm[d]:.1f}" for d in range(5)))

fig, ax = plt.subplots(figsize=(8.5, 7))
cols = {0: "#888", 1: "#2b6cb0", 2: "#2f9e44", 3: "#c0392b", 4: "#9b59b6"}
ax.scatter(st.lon, st.lat, s=18, c="#ccc", zorder=1)
for _, x in best.iterrows():
    ax.scatter(st.loc[x.sid, "lon"], st.loc[x.sid, "lat"], s=40 + 60 * (x.ratio - 1),
               c=cols[int(x.dow)], zorder=3, edgecolors="k", lw=.4)
for d in range(5):
    if (best.dow == d).any():
        ax.scatter([], [], c=cols[d], label=DOWS[d], s=60)
ax.legend(title="día del exceso vespertino", loc="lower right")
ax.set(title="Estaciones con tarde de diario 'encendida' (candidatas a pintxo-pote)",
       xticks=[], yticks=[])
fig.tight_layout(); fig.savefig("analysis/pintxopote.png", dpi=110)
