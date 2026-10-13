"""¿Son fiables las probabilidades del planificador de viajes?

Predicción = media histórica de la fracción del tiempo (vacía / llena / sin
eléctricas) por estación × tipo de día × hora, con encogimiento hacia la media
de la red cuando hay pocos días (k pseudo-días). Se entrena con un periodo y se
evalúa en las dos últimas semanas: calibración por tramos y Brier contra la
media de red (que ignora qué estación es).

Entrada: data/plan_hourly.csv.gz (sql/plan_hourly.sql)
Salida:  markdown por stdout

    python3 analysis/plan_calibration.py > analysis/plan_calibration.md
"""
import numpy as np
import pandas as pd

TEST0, TEST1 = "2026-09-29", "2026-10-13"
TARGETS = {"p_empty": "vacía", "p_full": "llena", "p_noelec": "sin eléctricas"}
KEY = ["station_id", "daytype", "hour"]

df = pd.read_csv("data/plan_hourly.csv.gz", parse_dates=["day"])
df = df[(df.n >= 10) & (df.hour >= 6)]                       # horas con servicio y cobertura
test = df[(df.day >= TEST0) & (df.day < TEST1)]


def predict(train, k):
    net = train.groupby(["daytype", "hour"])[list(TARGETS)].mean()
    g = train.groupby(KEY)[list(TARGETS)]
    s, n = g.sum(), g.size()
    out = s.join(n.rename("days"))
    pri = net.reindex(pd.MultiIndex.from_arrays([out.index.get_level_values(1), out.index.get_level_values(2)])).to_numpy()
    for i, t in enumerate(TARGETS):
        out[t] = (out[t] + k * pri[:, i]) / (out.days + k)
    return out[list(TARGETS)], net


WINDOWS = {"toda la historia": "2026-08-20", "desde el curso": "2026-09-08"}
print(f"# Calibración del planificador (test {TEST0} → 2026-10-12, {test.day.nunique()} días)\n")
print("Brier = error cuadrático de la probabilidad (menor es mejor); 'mejora' es frente a "
      "la media de red por tipo de día y hora (no sabe qué estación es).\n")
print("| entrenamiento | k | objetivo | Brier estación | Brier red | mejora |")
print("|---|---|---|---|---|---|")
best = None
for wname, w0 in WINDOWS.items():
    train = df[(df.day >= w0) & (df.day < TEST0)]
    for k in (0, 2, 5):
        pred, net = predict(train, k)
        j = test.join(pred, on=KEY, rsuffix="_hat").join(net, on=["daytype", "hour"], rsuffix="_net")
        tot = 0
        for t, lab in TARGETS.items():
            jj = j.dropna(subset=[t + "_hat"])
            b1 = ((jj[t + "_hat"] - jj[t]) ** 2).mean()
            b0 = ((jj[t + "_net"] - jj[t]) ** 2).mean()
            tot += b1
            print(f"| {wname} | {k} | {lab} | {b1:.4f} | {b0:.4f} | {(1 - b1 / b0) * 100:+.0f} % |")
        if best is None or tot < best[0]:
            best = (tot, wname, w0, k)

_, wname, w0, k = best
pred, _ = predict(df[(df.day >= w0) & (df.day < TEST0)], k)
j = test.join(pred, on=KEY, rsuffix="_hat")
print(f"\n## Calibración de la mejor variante ({wname}, k={k})\n")
print("Para cada tramo de probabilidad predicha: qué fracción del tiempo pasó de verdad.\n")
print("| predicho | " + " | ".join(f"{lab} (real, n)" for lab in TARGETS.values()) + " |")
print("|---|" + "---|" * len(TARGETS))
bins = [0, .05, .15, .3, .5, .7, 1.0001]
for lo, hi in zip(bins[:-1], bins[1:]):
    cells = []
    for t in TARGETS:
        jj = j.dropna(subset=[t + "_hat"])
        m = (jj[t + "_hat"] >= lo) & (jj[t + "_hat"] < hi)
        cells.append(f"{jj[m][t].mean():.2f} ({m.sum()})" if m.sum() else "—")
    print(f"| {lo:.2f}–{min(hi, 1):.2f} | " + " | ".join(cells) + " |")
dts = test.groupby("daytype").day.nunique()
print(f"\nDías de test por tipo: {dts.to_dict()}")
