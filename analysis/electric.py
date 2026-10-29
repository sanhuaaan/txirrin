"""Eléctricas frente a mecánicas: cuánto se usan, si la gente las prefiere y
cuánta demanda eléctrica se pierde por falta de ellas.

Entrada: data/electric.csv.gz (sql/electric.sql) + data/profiles.csv
Salida:  analysis/electric.png y markdown por stdout

    python3 analysis/electric.py > analysis/electric.md
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

H0, H1 = 6, 24
d = pd.read_csv("data/electric.csv.gz", parse_dates=["day"])
d = d[(d.hour >= H0) & (d.hour < H1)]
st = pd.read_csv("data/profiles.csv").groupby("station_id")[["name", "lat", "lon"]].first()
st["short"] = st.name.str.replace(r"^\s*\d+\s*[-–]*\s*", "", regex=True).str.split("/").str[0].str.strip().str.title()
ndays = d.groupby("daytype").day.nunique()
DT = {"lab": "laborable", "sab": "sábado", "dom": "domingo/festivo"}

tot = d[["dep_e", "dep_m", "arr_e", "arr_m"]].sum()
share = tot.dep_e / (tot.dep_e + tot.dep_m)
docked = d.groupby(["day", "hour"])[["avg_e", "avg_m"]].sum().mean()  # bicis ancladas de media en la red (de día)
# flota real por tipo: de madrugada la red está cerrada y todo lo que presta está anclado
fn = pd.read_csv("data/fleet_night.csv", parse_dates=["day"])
fleet = fn[["e", "m"]].mean().rename({"e": "avg_e", "m": "avg_m"})
lab = d[d.daytype == "lab"]
byh = lab.groupby("hour").agg(dep_e=("dep_e", "sum"), dep_m=("dep_m", "sum"), deb=("dep_e_both", "sum"), dmb=("dep_m_both", "sum"),
                              ae=("avg_e_both", "mean"), am=("avg_m_both", "mean"), noe=("p_noelec", "mean"), nom=("p_nomech", "mean"))
nlab = lab.day.nunique()

# preferencia: salidas por bici disponible y hora, solo mientras había de los dos tipos
# (así la falta de eléctricas no se confunde con falta de ganas)
both = d[(d.avg_e_both > 0) & (d.avg_m_both > 0)]
rate_e = both.dep_e_both.sum() / both.avg_e_both.sum()
rate_m = both.dep_m_both.sum() / both.avg_m_both.sum()
pref = rate_e / rate_m

# demanda eléctrica perdida: horas sin eléctricas (con mecánicas) × tasa eléctrica por hora de esa estación
r_e = d[d.p_noelec < 0.8].groupby(["station_id", "daytype", "hour"]).apply(
    lambda g: g.dep_e.sum() / max(1e-9, (1 - g.p_noelec).sum())).rename("re")
dd = d.join(r_e, on=["station_id", "daytype", "hour"])
dd["lost_e"] = dd.p_noelec * dd.re.fillna(0)
lost_day = dd.groupby("day").lost_e.sum().mean()
dep_day = d.groupby("day").dep_e.sum().mean()
lost_st = dd.groupby("station_id").lost_e.sum() / d.day.nunique()
noe_st = d.groupby("station_id").p_noelec.mean()

print(f"# Eléctricas frente a mecánicas ({d.day.nunique()} días: {ndays.get('lab',0)} laborables, "
      f"{ndays.get('sab',0)} sábados, {ndays.get('dom',0)} domingos/festivos; horas {H0}-{H1})\n")
print("## Cuánto se usan\n")
print(f"- Flota (ancladas de madrugada, red cerrada): **{fleet.avg_e:.0f} eléctricas** y **{fleet.avg_m:.0f} mecánicas** "
      f"({fleet.avg_e / (fleet.avg_e + fleet.avg_m) * 100:.0f} % eléctricas); las eléctricas oscilan entre {fn.e.min():.0f} y {fn.e.max():.0f} "
      f"según la noche (el operador retira parte a cargar). De día quedan ancladas de media {docked.avg_e:.0f} y {docked.avg_m:.0f}.")
print(f"- Salidas: **{share * 100:.0f} % eléctricas** ({tot.dep_e / d.day.nunique():.0f} frente a {tot.dep_m / d.day.nunique():.0f} al día).")
print(f"- Rotación: cada eléctrica sale **{tot.dep_e / d.day.nunique() / fleet.avg_e:.1f} veces al día**; cada mecánica, "
      f"{tot.dep_m / d.day.nunique() / fleet.avg_m:.1f}. En circulación a la vez, de media: "
      f"{(1 - docked.avg_e / fleet.avg_e) * 100:.0f} % de las eléctricas y {(1 - docked.avg_m / fleet.avg_m) * 100:.0f} % de las mecánicas.")
bydt = d.groupby("daytype")[["dep_e", "dep_m"]].sum()
print("- Cuota eléctrica por tipo de día: " + ", ".join(f"{DT[k]} {r.dep_e / (r.dep_e + r.dep_m) * 100:.0f} %" for k, r in bydt.iterrows()) + ".")
print(f"\n## ¿La gente las prefiere?\n")
print(f"- Con los dos tipos disponibles en la estación, una eléctrica sale **{pref:.1f} veces más a menudo** que una mecánica "
      f"({rate_e:.2f} frente a {rate_m:.2f} salidas por bici y hora). Ojo: también refleja que las eléctricas son pocas y cada una rota más.")
peak = byh.assign(pr=(byh.deb / byh.ae) / (byh.dmb / byh.am))
print(f"- Preferencia por hora (laborable): máxima a las {int(peak.pr.idxmax())} h (×{peak.pr.max():.1f}), mínima a las {int(peak.pr.idxmin())} h (×{peak.pr.min():.1f}).")
print(f"\n## Dónde y cuándo faltan\n")
print(f"- Tiempo sin eléctricas (con mecánicas disponibles): **{d.p_noelec.mean() * 100:.0f} %** del horario; sin mecánicas (con eléctricas): {d.p_nomech.mean() * 100:.0f} %.")
print(f"- Hora más seca de eléctricas en laborable: {int(byh.noe.idxmax())} h ({byh.noe.max() * 100:.0f} % de las estaciones-hora sin ninguna).")
print(f"- **Demanda eléctrica no atendida** (cota superior): hasta ~**{lost_day:.0f} salidas al día** habrían sido en eléctrica si siempre hubiera "
      f"({lost_day / (dep_day + lost_day) * 100:.0f} % de la demanda eléctrica estimada). Parte se hace en mecánica, parte se pierde; "
      "es cota superior porque extrapola la tasa de cuando hay eléctricas, que es alta justo porque escasean.")
print("\nLas que más tiempo pasan sin eléctricas:\n")
print("| estación | sin eléctricas | eléctricas perdidas/día |")
print("|---|---|---|")
for sid in noe_st.sort_values(ascending=False).head(10).index:
    print(f"| {st.short.get(sid, sid)} | {noe_st[sid] * 100:.0f} % | {lost_st.get(sid, 0):.1f} |")

# ---------- figura ----------
fig, axs = plt.subplots(2, 2, figsize=(13, 9)); ax = axs.ravel()
h = byh.index
dk = lab.groupby(["day", "hour"])[["avg_e", "avg_m"]].sum().groupby("hour").mean()
ax[3].plot(dk.index, (1 - dk.avg_e / fleet.avg_e) * 100, "o-", color="#e6a23c", lw=2, label="eléctricas")
ax[3].plot(dk.index, (1 - dk.avg_m / fleet.avg_m) * 100, "o-", color="#8899aa", lw=2, label="mecánicas")
ax[3].set(title="% de la flota en circulación, laborable", xlabel="hora local", ylabel="%", ylim=(0, None)); ax[3].legend(); ax[3].grid(alpha=.3)
ax[0].bar(h, byh.dep_m / nlab, color="#8899aa", label="mecánicas")
ax[0].bar(h, byh.dep_e / nlab, bottom=byh.dep_m / nlab, color="#e6a23c", label="eléctricas")
ax[0].set(title="Salidas por hora, laborable (media/día)", xlabel="hora local"); ax[0].legend(); ax[0].grid(alpha=.3, axis="y")
ax[1].plot(h, peak.pr, "o-", color="#e6a23c", lw=2)
ax[1].axhline(1, color="#999", ls="--", lw=1)
ax[1].set(title="Preferencia: salidas por eléctrica / por mecánica\n(solo con ambas disponibles)", xlabel="hora local", ylim=(0, max(2.5, peak.pr.max() * 1.1)))
ax[1].grid(alpha=.3)
ax[2].plot(h, byh.noe * 100, "o-", color="#e66767", lw=2, label="sin eléctricas")
ax[2].plot(h, byh.nom * 100, "o-", color="#5b9bff", lw=2, label="sin mecánicas")
ax[2].set(title="% de estaciones sin un tipo, laborable", xlabel="hora local", ylabel="%"); ax[2].legend(); ax[2].grid(alpha=.3)
fig.tight_layout(); fig.savefig("analysis/electric.png", dpi=110)
