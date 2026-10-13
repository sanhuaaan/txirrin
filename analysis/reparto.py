"""Reparto óptimo, primera vuelta (etapas 1, 3 sin meteo y 4 de reparto-optimo.md).

1. Medir: tiempo fuera de banda (vacía o llena) por estación, tipo de día y hora.
3. Marea: tasas de salidas y llegadas por estación × tipo de día × hora,
   corregidas de censura (una estación vacía no registra las salidas que pierde:
   la tasa se estima solo con las horas en que no estaba vacía; igual con las
   llegadas y las horas llena).
4. Colocación: cuántas bicis debería tener cada estación a las 06:00 para
   minimizar el tiempo fuera de banda del día, con la flota que hay, resuelto
   exacto por programación dinámica sobre un modelo de fluido (tasas medias,
   paso de 15 min). Y la ruta orientativa del camión que lo materializaría.

Entrada: data/plan_hourly.csv.gz, data/events.csv.gz, data/stock06.csv, data/profiles.csv
Salida:  analysis/reparto.png y markdown por stdout

    python3 analysis/reparto.py > analysis/reparto.md
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

H0, H1 = 6, 24                                # horas de servicio
CENSOR = 0.8                                  # >80 % de la hora vacía/llena: no sirve para estimar la tasa
STEP = 4                                      # pasos por hora en la simulación
MIN_DAYS = 5

st = pd.read_csv("data/profiles.csv").groupby("station_id")[["name", "lat", "lon"]].first()
cap = pd.read_csv("data/stock06.csv").set_index("station_id")
st = st.join(cap[["capacity", "bikes6"]], how="inner")
st["short"] = st.name.str.replace(r"^\s*\d+\s*[-–]*\s*", "", regex=True).str.split("/").str[0].str.strip().str.title()
M_DEG = 111320.0
st["x"] = (st.lon - st.lon.mean()) * M_DEG * np.cos(np.radians(st.lat.mean()))
st["y"] = (st.lat - st.lat.mean()) * M_DEG

ph = pd.read_csv("data/plan_hourly.csv.gz", parse_dates=["day"])
ph = ph[(ph.n >= 10) & (ph.hour >= H0) & ph.station_id.isin(st.index)]

ev = pd.read_csv("data/events.csv.gz", parse_dates=["ts"])
ev["ts"] = ev.ts.dt.tz_convert("Europe/Madrid")
ev["day"] = pd.to_datetime(ev.ts.dt.date); ev["hour"] = ev.ts.dt.hour
evh = ev.groupby(["station_id", "day", "hour"])[["dep", "arr"]].sum().reset_index()
d = ph.merge(evh, on=["station_id", "day", "hour"], how="left").fillna({"dep": 0, "arr": 0})

DT = {"lab": "laborable", "sab": "sábado", "dom": "domingo/festivo"}
ndays = d.groupby("daytype").day.nunique()

# ---------- etapa 1: medir ----------
d["oob"] = d.p_empty + d.p_full
e1 = d.groupby(["station_id", "daytype"]).agg(p_e=("p_empty", "mean"), p_f=("p_full", "mean"), oob=("oob", "mean"))
net1 = d.groupby("daytype")[["p_empty", "p_full", "oob"]].mean()

# ---------- etapa 3: marea corregida ----------
d["dep_ok"] = np.where(d.p_empty < CENSOR, d.dep / (1 - d.p_empty), np.nan)
d["arr_ok"] = np.where(d.p_full < CENSOR, d.arr / (1 - d.p_full), np.nan)
rates = d.groupby(["station_id", "daytype", "hour"]).agg(dep=("dep_ok", "mean"), arr=("arr_ok", "mean"),
                                                        dep_obs=("dep", "mean"), arr_obs=("arr", "mean"), days=("day", "nunique"))
rates["dep"] = rates.dep.fillna(rates.dep_obs); rates["arr"] = rates.arr.fillna(rates.arr_obs)
# conservación: las salidas recuperadas de la censura llegan a algún sitio. Sin
# esto la red entera se desangra en la simulación (salidas > llegadas). Se
# reparten proporcionalmente a las llegadas de cada hora y tipo de día.
k = rates.groupby(level=[1, 2]).apply(lambda g: g.dep.sum() / max(1e-9, g.arr.sum()))
rates["arr"] = rates.arr * k.reindex(pd.MultiIndex.from_arrays([rates.index.get_level_values(1), rates.index.get_level_values(2)])).to_numpy()

# ---------- etapa 4: simulación y colocación ----------
def simulate(dep, arr, s0, c):
    """Fracción de pasos fuera de banda partiendo de s0 bicis a las 06:00. dep/arr: tasas por hora."""
    s, oob, n = float(s0), 0, 0
    for h in range(len(dep)):
        for _ in range(STEP):
            s = min(c, max(0.0, s + (arr[h] - dep[h]) / STEP))
            oob += (s <= 0.5) or (s >= c - 0.5); n += 1
    return oob / n

def plan(dt):
    hours = list(range(H0, H1))
    cost, rows = {}, []
    for sid in st.index:
        r = rates.loc[sid, dt].reindex(hours) if (sid, dt) in rates.index.droplevel(2) else None
        if r is None or r.days.max() < MIN_DAYS:
            continue
        dep, arr = r.dep.fillna(0).to_numpy(), r.arr.fillna(0).to_numpy()
        c = int(st.loc[sid, "capacity"])
        cost[sid] = np.array([simulate(dep, arr, s0, c) for s0 in range(c + 1)])
    sids = list(cost)
    B = int(round(st.loc[sids, "bikes6"].sum()))
    # DP exacta: mejor coste acumulado con b bicis repartidas entre las i primeras estaciones
    INF = 1e9
    best = np.full(B + 1, INF); best[0] = 0
    choice = []
    for sid in sids:
        cst = cost[sid]; new = np.full(B + 1, INF); arg = np.zeros(B + 1, dtype=int)
        for b in range(B + 1):
            k = np.arange(0, min(len(cst), b + 1))
            v = best[b - k] + cst[k]
            j = int(np.argmin(v)); new[b], arg[b] = v[j], k[j]
        best, choice = new, choice + [arg]
    b, s_opt = B, {}
    for sid, arg in zip(reversed(sids), reversed(choice)):
        s_opt[sid] = int(arg[b]); b -= s_opt[sid]
    out = pd.DataFrame({"sid": sids})
    out["now"] = [int(round(st.loc[s, "bikes6"])) for s in sids]
    out["opt"] = [s_opt[s] for s in sids]
    out["cost_now"] = [cost[s][min(st.loc[s, "capacity"], out.now[i])] for i, s in enumerate(sids)]
    out["cost_opt"] = [cost[s][out.opt[i]] for i, s in enumerate(sids)]
    out["obs"] = [e1.loc[(s, dt), "oob"] if (s, dt) in e1.index else np.nan for s in sids]
    return out.set_index("sid")

def route(moves):
    """Ruta orientativa: vecino más cercano por las estaciones con movimiento. km en línea recta."""
    ids = list(moves.index); km = 0.0; cur = max(ids, key=lambda s: moves[s])   # arranca donde más sobra
    order = [cur]; ids.remove(cur)
    while ids:
        nxt = min(ids, key=lambda s: np.hypot(st.x[s] - st.x[cur], st.y[s] - st.y[cur]))
        km += np.hypot(st.x[nxt] - st.x[cur], st.y[nxt] - st.y[cur]) / 1000; cur = nxt
        order.append(cur); ids.remove(cur)
    return order, km

HS = (H1 - H0)
print(f"# Reparto óptimo, primera vuelta ({ndays.get('lab', 0)} laborables, {ndays.get('sab', 0)} sábados, "
      f"{ndays.get('dom', 0)} domingos/festivos; horas {H0}-{H1} h)\n")
print("## Etapa 1 · Cuánto tiempo falla la red\n")
print("| tipo de día | vacía | llena | fuera de banda | horas/día por estación |")
print("|---|---|---|---|---|")
for dt, r in net1.iterrows():
    print(f"| {DT[dt]} | {r.p_empty*100:.1f} % | {r.p_full*100:.1f} % | **{r.oob*100:.1f} %** | {r.oob*HS:.1f} h |")
worst = e1.xs("lab", level=1).sort_values("oob", ascending=False).head(12)
print("\nLas que más fallan en laborable:\n")
print("| estación | vacía | llena | fuera de banda |")
print("|---|---|---|---|")
for sid, r in worst.iterrows():
    print(f"| {st.short[sid]} | {r.p_e*100:.0f} % | {r.p_f*100:.0f} % | **{r.oob*100:.0f} %** |")

print("\n## Etapa 3 · La marea, corregida de censura\n")
lab = rates.xs("lab", level=1)
corr = (lab.dep.sum() / max(1e-9, lab.dep_obs.sum()) - 1) * 100
print(f"- Salidas estimadas en laborable: {lab.dep.sum()/len(st):.0f}/día por estación "
      f"({corr:+.0f} % sobre las observadas: lo que las estaciones vacías dejaron de prestar).")
hid = lab.groupby("station_id").apply(lambda g: (g.dep - g.dep_obs).sum()).sort_values(ascending=False).head(5)
print("- Dónde más demanda se pierde por vacío (salidas/día no atendidas): " +
      ", ".join(f"{st.short[s]} {v:.0f}" for s, v in hid.items()) + ".")

results = {}
for dt in ["lab", "sab", "dom"]:
    if ndays.get(dt, 0) >= MIN_DAYS:
        results[dt] = plan(dt)
P = results["lab"]
print("\n## Etapa 4 · Colocación a las 06:00 (laborable)\n")
sim_now, obs = P.cost_now.mean(), P.obs.mean()
print(f"- **Validación del simulador**: con el stock real de las 06:00 predice {sim_now*100:.1f} % fuera de banda; "
      f"lo observado es {obs*100:.1f} % (correlación entre estaciones {np.corrcoef(P.cost_now, P.obs)[0,1]:.2f}). "
      + ("Subestima: usa tasas medias y no ve los días malos." if sim_now < obs * 0.8 else
         "Sobreestima: el modelo de fluido exagera la deriva." if sim_now > obs * 1.25 else "Razonable para comparar repartos.")
      + " Las mejoras son relativas, no una promesa.")
print(f"- Flota en juego: {P.now.sum()} bicis a las 06:00 entre {len(P)} estaciones.")
print(f"- Fuera de banda, simulado: **{sim_now*100:.1f} % → {P.cost_opt.mean()*100:.1f} %** con el reparto óptimo "
      f"({(1 - P.cost_opt.mean()/max(1e-9, sim_now))*100:.0f} % menos).")
for dt in ("sab", "dom"):
    if dt in results:
        R = results[dt]; print(f"- {DT[dt].capitalize()}: {R.cost_now.mean()*100:.1f} % → {R.cost_opt.mean()*100:.1f} %.")
mv = (P.opt - P.now); mv = mv[mv.abs() >= 2].sort_values()
print(f"\nMovimientos de 2 o más bicis ({len(mv)} estaciones, {mv[mv > 0].sum()} bicis cambian de sitio):\n")
print("| estación | hoy a las 06:00 | óptimo | mover | fuera de banda hoy → óptimo |")
print("|---|---|---|---|---|")
for sid, m in pd.concat([mv.head(10), mv.tail(10)]).drop_duplicates().items():
    r = P.loc[sid]
    print(f"| {st.short[sid]} | {int(r.now)} | {int(r.opt)} | {int(m):+d} | {r.cost_now*100:.0f} % → {r.cost_opt*100:.0f} % |")
order, km = route(mv)
print(f"\nRuta orientativa (vecino más cercano, línea recta): {len(order)} paradas, ~{km:.1f} km, empezando en {st.short[order[0]]}.")

# ---------- figura ----------
fig, ax = plt.subplots(1, 2, figsize=(14, 6))
ax[0].scatter(st.x, st.y, s=10, c="#bbb")
for sid, m in (P.opt - P.now).items():
    if abs(m) >= 1:
        ax[0].scatter(st.x[sid], st.y[sid], s=25 + 18 * abs(m), c="#2f9e44" if m > 0 else "#c0392b", alpha=.75, edgecolors="k", lw=.3)
for s in mv.index: ax[0].annotate(f"{mv[s]:+d}", (st.x[s], st.y[s]), fontsize=7, ha="center", va="center", color="w")
ax[0].plot([st.x[s] for s in order], [st.y[s] for s in order], c="#555", lw=.6, alpha=.6)
ax[0].set(title="Reparto a las 06:00 (laborable): verde añade, rojo retira; línea = ruta", xticks=[], yticks=[])
ax[0].set_aspect("equal")
top = P.assign(gain=P.cost_now - P.cost_opt).sort_values("gain", ascending=False).head(15)
yy = np.arange(len(top))
ax[1].barh(yy + .2, top.cost_now * 100, .4, color="#888", label="hoy")
ax[1].barh(yy - .2, top.cost_opt * 100, .4, color="#2b6cb0", label="óptimo")
ax[1].set_yticks(yy); ax[1].set_yticklabels([st.short[s] for s in top.index], fontsize=8); ax[1].invert_yaxis()
ax[1].set(xlabel="% del día fuera de banda (simulado)", title="Las 15 que más mejoran"); ax[1].legend(); ax[1].grid(alpha=.3, axis="x")
fig.tight_layout(); fig.savefig("analysis/reparto.png", dpi=110)
