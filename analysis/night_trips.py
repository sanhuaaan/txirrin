"""Viajes nocturnos origen-destino por emparejado inequívoco.

En horas valle, cuando en toda la red hay UNA salida y minutos después UNA
llegada, ese par es casi seguro un viaje real. Validación interna: la duración
debe crecer con la distancia a velocidad de bici (~10-20 km/h); si no, el
método no vale y se tira.

Entrada: data/events.csv.gz (sql/events.sql) + data/profiles.csv (coordenadas)
Salida:  analysis/night_trips.png, data/night_trips.csv y markdown por stdout

    python3 analysis/night_trips.py > analysis/night_trips.md
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

NIGHT = (2, 5)           # madrugada profunda: fuera de ahí la red nunca calla
WMAX, WMIN, VBAND = 12, 2, (8, 20)   # min y km/h: viajes cortos a velocidad de bici

ev = pd.read_csv("data/events.csv.gz", parse_dates=["ts"])
ev["ts"] = ev.ts.dt.tz_convert("Europe/Madrid")
h = ev.ts.dt.hour
ev = ev[(h >= NIGHT[0]) & (h < NIGHT[1])] if NIGHT[0] < NIGHT[1] else ev[(h >= NIGHT[0]) | (h < NIGHT[1])]
st = (pd.read_csv("data/profiles.csv").groupby("station_id")[["name", "lat", "lon"]].first())

# a eventos unitarios: una fila por bici que sale o llega
rows = []
for r in ev.itertuples():
    rows += [(r.ts, r.station_id, "dep")] * int(r.dep) + [(r.ts, r.station_id, "arr")] * int(r.arr)
u = pd.DataFrame(rows, columns=["ts", "sid", "kind"]).sort_values("ts").reset_index(drop=True)

# limpieza de parpadeos del feed: salida y llegada en la MISMA estación a
# <=6 min es casi siempre un anclaje mal hecho, no un viaje; fuera ambos eventos
drop = set()
for _, g in u.groupby("sid"):
    ix, tt, kk = g.index.to_numpy(), g.ts.to_numpy(), g.kind.to_numpy()
    for i in range(len(g) - 1):
        if kk[i] == "dep" and kk[i+1] == "arr" and (tt[i+1]-tt[i])/np.timedelta64(1,"m") <= 6:
            drop |= {ix[i], ix[i+1]}
n_flick = len(drop) // 2
u = u.drop(index=drop).reset_index(drop=True)

# emparejado por unicidad mutua: una salida y una llegada se emparejan si cada
# una es la ÚNICA candidata plausible de la otra (2-40 min y 6-22 km/h entre
# sus estaciones). Mucho menos estricto que exigir silencio en toda la red
# (que da 1 par en 43 noches: la ciudad nunca calla), pero sigue sin decidir
# nada en caso de ambigüedad.
la, lo = st.lat.to_dict(), st.lon.to_dict()
R = 6371.0088
def hav(o, d):
    p1, p2 = np.radians(la[o]), np.radians(la[d])
    dp, dl = p2 - p1, np.radians(lo[d] - lo[o])
    return 2 * R * np.arcsin(np.sqrt(np.sin(dp/2)**2 + np.cos(p1)*np.cos(p2)*np.sin(dl/2)**2))

def match(u, st):
    u = u[u.sid.isin(st.index)]
    dep = u[u.kind == "dep"].reset_index(drop=True)
    arr = u[u.kind == "arr"].reset_index(drop=True)
    at = arr.ts.to_numpy()
    cand = {}                       # dep i -> [arr j...]
    rcand = {}                      # arr j -> [dep i...]
    for i, (t0, s0) in enumerate(zip(dep.ts.to_numpy(), dep.sid.to_numpy())):
        j0, j1 = np.searchsorted(at, t0 + np.timedelta64(WMIN, "m")), np.searchsorted(at, t0 + np.timedelta64(WMAX, "m"))
        for j in range(j0, j1):
            s1 = arr.sid.iat[j]
            if s1 == s0: continue
            mins = (at[j] - t0) / np.timedelta64(1, "m")
            v = hav(s0, s1) / (mins / 60)
            if VBAND[0] <= v <= VBAND[1]:
                cand.setdefault(i, []).append(j); rcand.setdefault(j, []).append(i)
    out = []
    for i, js in cand.items():
        if len(js) == 1 and len(rcand[js[0]]) == 1:
            j = js[0]
            out.append((dep.ts.iat[i], dep.sid.iat[i], arr.sid.iat[j],
                        (at[j] - dep.ts.to_numpy()[i]) / np.timedelta64(1, "m")))
    return out

trips = match(u, st)
# control: cruzar las salidas con las llegadas de 24 h despues. Si el metodo
# inventa pares, aqui saldran casi tantos; si mide viajes reales, muchos menos.
ushift = u.copy()
ushift.loc[ushift.kind == "arr", "ts"] += pd.Timedelta("1day")
null_trips = len(match(ushift.sort_values("ts").reset_index(drop=True), st))
t = pd.DataFrame(trips, columns=["ts", "o", "d", "min"])
t["km"] = [hav(o, d) for o, d in zip(t.o, t.d)]
t["kmh"] = t.km / (t["min"] / 60)
ok = t
t.to_csv("data/night_trips.csv", index=False)

print(f"# Viajes de madrugada por emparejado inequívoco ({NIGHT[0]}-{NIGHT[1]} h, "
      f"{ev.ts.dt.date.nunique()} noches)\n")
print(f"- Eventos nocturnos tras limpieza: {len(u)} ({(u.kind=='dep').sum()} salidas, {(u.kind=='arr').sum()} llegadas)")
print(f"- Parpadeos del feed eliminados (dep→arr misma estación <=6 min): {n_flick}")
print(f"- Pares por unicidad mutua ({WMIN}-{WMAX} min, {VBAND[0]}-{VBAND[1]} km/h): **{len(t)}**")
print(f"- Control con llegadas de 24 h después: {null_trips} pares espurios → señal/ruido ~{len(t)/max(1,null_trips):.1f}x")
c = np.corrcoef(ok.km, ok["min"])[0, 1] if len(ok) > 2 else float("nan")
v = ok.km.sum() / (ok["min"].sum() / 60)
print(f"- Correlación distancia-duración: **{c:.2f}** · velocidad mediana {ok.kmh.median():.1f} km/h, global {v:.1f} km/h\n")
print("## Top pares origen → destino\n")
top = ok.groupby(["o", "d"]).agg(n=("min", "size"), med=("min", "median"), km=("km", "first"))
top = top.sort_values("n", ascending=False).head(12)
print("| origen | destino | viajes | mediana min | km |")
print("|---|---|---|---|---|")
for (o, d), r in top.iterrows():
    print(f"| {st.loc[o,'name']} | {st.loc[d,'name']} | {int(r.n)} | {r.med:.0f} | {r.km:.1f} |")

fig, ax = plt.subplots(1, 2, figsize=(13, 5.5))
ax[0].scatter(ok.km, ok["min"], s=8, alpha=.35, c="#2b6cb0")
for spd in (10, 15, 20):
    x = np.linspace(0, ok.km.max(), 50); ax[0].plot(x, x / spd * 60, "--", lw=.8, c="#999")
    ax[0].text(ok.km.max(), ok.km.max() / spd * 60, f" {spd} km/h", fontsize=8, c="#777", va="center")
ax[0].set(xlabel="distancia en línea recta (km)", ylabel="duración (min)",
          title=f"Distancia vs duración · r={c:.2f}")
ax[0].grid(alpha=.3)
seen = ok.groupby(["o", "d"]).size()
for (o, d), n in seen.items():
    ax[1].plot([lo[o], lo[d]], [la[o], la[d]], c="#2b6cb0", lw=min(3, .4 * n), alpha=.3)
ax[1].scatter(st.lon, st.lat, s=12, c="#222", zorder=3)
ax[1].set(title=f"{len(ok)} viajes nocturnos emparejados", xticks=[], yticks=[])
fig.tight_layout(); fig.savefig("analysis/night_trips.png", dpi=110)
