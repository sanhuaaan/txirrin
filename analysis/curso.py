"""Antes/después del inicio de curso (2026-09-07).

Entrada: data/curso.csv + data/curso_trips.csv (ver sql/curso*.sql).
Salida:  analysis/curso.png y markdown por stdout.

    python3 analysis/curso.py > analysis/curso.md
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CORTE = "2026-09-07"
df = pd.read_csv("data/curso.csv")
tr = pd.read_csv("data/curso_trips.csv", parse_dates=["day"])

# --- viajes por día: solo días completos (720 snapshots = 24 h a 2 min) ---
tr["trips"] = (tr.dep + tr.arr) / 2
full = tr[tr.n_snaps >= 700].copy()
full["period"] = np.where(full.day < CORTE, "pre", "post")
full["weekend"] = full.day.dt.dayofweek >= 5
lab = full.groupby(["period", "weekend"]).trips.mean().unstack()

# --- perfil horario de red, laborables, ponderado por snapshots ---
wd = df[df.daytype == "weekday"].copy()
wd["w"] = wd.occ * wd.n
net = wd.groupby(["period", "hour"]).apply(lambda g: g.w.sum() / g.n.sum()).unstack()

# --- curvas por estación y quién se mueve más ---
piv = wd.pivot_table(index="station_id", columns=["period", "hour"], values="occ")
pre, post = piv["pre"], piv["post"]
ok = pre.notna().sum(1).ge(20) & post.notna().sum(1).ge(20)   # estaciones con datos en ambos
pre, post = pre[ok].interpolate(axis=1), post[ok].interpolate(axis=1)
delta = post - pre
meta = df.groupby("station_id")[["name", "lat", "lon"]].first().loc[delta.index]
meta["shift"] = delta.mean(axis=1)                     # cambio de nivel medio
meta["shape"] = (delta.sub(delta.mean(axis=1), axis=0) ** 2).mean(axis=1) ** 0.5  # cambio de forma
movers = meta.reindex(meta["shape"].sort_values(ascending=False).index)

def cap(s):  # capacidad no viaja en este CSV; el nombre ya lleva el número
    return s

print("# Antes / después del inicio de curso (corte 2026-09-07)\n")
d0, d1 = tr.day.min().date(), tr.day.max().date()
print(f"Datos {d0} → {d1}. `pre` = verano (incluye el final de Semana Grande),")
print("`post` = curso (una semana lectiva). Meteo sin controlar: tómese como foto, no como ley.\n")
print("## Viajes estimados por día (regla del timelapse, días completos)\n")
print("| | laborable | fin de semana |")
print("|---|---|---|")
for p in ["pre", "post"]:
    print(f"| {p} | {lab.loc[p, False]:.0f} | {lab.loc[p, True]:.0f} |")
g = (lab.loc["post", False] / lab.loc["pre", False] - 1) * 100
print(f"\nLaborables: **{g:+.1f} %** con el curso empezado.\n")
print("## Estaciones que más cambian de perfil (laborables, cambio de forma)\n")
print("| estación | Δ nivel | Δ forma (rms) | lectura |")
print("|---|---|---|---|")
for sid, r in movers.head(10).iterrows():
    d = delta.loc[sid]
    up, dn = d.idxmax(), d.idxmin()
    lect = f"gana a las {up}h, pierde a las {dn}h"
    print(f"| {r['name']} | {r['shift']:+.2f} | {r['shape']:.2f} | {lect} |")
print("\n(Δ nivel: ocupación media post−pre; Δ forma: cuánto cambia la curva además del nivel.)")

# --- figura: perfil de red, viajes/día y mapa del cambio ---
fig, ax = plt.subplots(1, 3, figsize=(16, 4.5))
for p, c in [("pre", "#888"), ("post", "#c0392b")]:
    ax[0].plot(net.columns, net.loc[p], c, label=p, lw=2)
ax[0].set(title="Ocupación media de red, laborables", xlabel="hora local", ylabel="ocupación")
ax[0].legend(); ax[0].grid(alpha=.3)
# alpha no admite array en esta matplotlib: se mete en el color RGBA
col = [(.53,.53,.53,a) if d < pd.Timestamp(CORTE) else (.75,.22,.17,a)
       for d, a in zip(full.day, np.where(full.weekend, .45, 1.0))]
ax[1].bar(full.day, full.trips, color=col)
ax[1].axvline(pd.Timestamp(CORTE), ls="--", c="k", lw=1)
ax[1].set(title="Viajes estimados por día (findes atenuados)")
ax[1].tick_params(axis="x", rotation=45)
sc = ax[2].scatter(meta.lon, meta.lat, c=meta["shift"], cmap="coolwarm", vmin=-.15, vmax=.15, s=60, edgecolors="k", lw=.3)
fig.colorbar(sc, ax=ax[2], label="Δ ocupación media")
ax[2].set(title="Cambio de nivel post−pre por estación", xticks=[], yticks=[])
fig.tight_layout(); fig.savefig("analysis/curso.png", dpi=110)
