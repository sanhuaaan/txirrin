"""Afinado de la alarma "vacía en 30 min" sobre el raw del backtest zero-shot.

Barre el umbral de la banda baja (q10 <= θ) y del punto (pred <= θ), dibuja la
curva precision/recall completa, elige puntos de trabajo y comprueba con corte
temporal (train/test) si personalizar el umbral por cluster aporta algo.

Entrada: data/forecast_eval_raw.csv.gz + data/profiles_clusters.csv
Salida:  analysis/alarm_tuning.png y markdown por stdout

    python3 analysis/alarm_tuning.py > analysis/alarm_tuning.md
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

EMPTY, H = 0.5, "30min"
SPLIT = "2026-09-22"            # train: 2 primeras semanas; test: los ~9 días finales

r = pd.read_csv("data/forecast_eval_raw.csv.gz", parse_dates=["t0"])
t = r[(r.model == "timesfm") & (r.h == H) & (r["last"] > EMPTY)].copy()  # transiciones
t["te"] = t.truth <= EMPTY
cl = pd.read_csv("data/profiles_clusters.csv").set_index("station_id").cluster
t["cluster"] = t.station_id.map(cl).fillna(-1).astype(int)   # -1: estaciones planas sin cluster
t["hod"] = t.t0.dt.hour

def pr(alarm, te):
    tp = (alarm & te).sum()
    return tp / max(1, alarm.sum()), tp / max(1, te.sum())

THETAS = np.arange(0, 5.001, 0.25)
curves = {}
for name, col in [("q10", "q10"), ("punto", "pred")]:
    curves[name] = [pr(t[col] <= th, t.te) for th in THETAS]

print(f"# Afinado de la alarma 'vacía en 30 min' (transiciones, {t.te.sum()} vaciados en {len(t)} casos)\n")
print("## Barrido del umbral θ (alarma si q10 <= θ)\n")
print("| θ | precisión | recall | | θ (punto) | precisión | recall |")
print("|---|---|---|---|---|---|---|")
for i, th in enumerate(THETAS):
    if th in (0, 0.5, 1, 1.5, 2, 3):
        pq, rq = curves["q10"][i]; pp, rp = curves["punto"][i]
        print(f"| {th:.1f} | {pq:.2f} | {rq:.2f} | | {th:.1f} | {pp:.2f} | {rp:.2f} |")

# puntos de trabajo sobre la curva q10
f1 = [2*p*rc/max(1e-9, p+rc) for p, rc in curves["q10"]]
best = int(np.argmax(f1))
prec_ok = [i for i, (p, _) in enumerate(curves["q10"]) if p >= 0.5]
print(f"\n- Mejor F1: θ={THETAS[best]:.2f} → precisión {curves['q10'][best][0]:.2f}, recall {curves['q10'][best][1]:.2f}")
if prec_ok:
    i = max(prec_ok, key=lambda i: curves["q10"][i][1])
    print(f"- Máximo recall con precisión >= 0.5: θ={THETAS[i]:.2f} → precisión {curves['q10'][i][0]:.2f}, recall {curves['q10'][i][1]:.2f}")

# ¿umbral por cluster? decidido en train, juzgado en test
tr, te_ = t[t.t0 < SPLIT], t[t.t0 >= SPLIT]
def best_theta(g):
    f = [2*p*rc/max(1e-9, p+rc) for p, rc in (pr(g.q10 <= th, g.te) for th in THETAS)]
    return THETAS[int(np.argmax(f))]
th_g = best_theta(tr)
th_c = tr.groupby("cluster").apply(best_theta)
p1, r1 = pr(te_.q10 <= th_g, te_.te)
p2, r2 = pr(te_.q10 <= te_.cluster.map(th_c).fillna(th_g), te_.te)
print(f"\n## ¿Umbral por cluster? (elegido en train, evaluado en test)\n")
print(f"- Global θ={th_g:.2f}: precisión {p1:.2f}, recall {r1:.2f}")
print(f"- Por cluster {dict((int(k), float(v)) for k, v in th_c.items())}: precisión {p2:.2f}, recall {r2:.2f}")

# dónde funciona: por cluster y por tramo horario, en el punto de mejor F1
TH = THETAS[best]
t["alarm"] = t.q10 <= TH
print(f"\n## Dónde acierta (θ={TH:.2f})\n")
print("| segmento | precisión | recall | vaciados |")
print("|---|---|---|---|")
for c, g in t.groupby("cluster"):
    p, rc = pr(g.alarm, g.te)
    print(f"| cluster {c} | {p:.2f} | {rc:.2f} | {g.te.sum()} |")
for lab, m in [("madrugada 0-7", (t.hod < 7)), ("mañana 7-13", (t.hod >= 7) & (t.hod < 13)),
               ("tarde 13-20", (t.hod >= 13) & (t.hod < 20)), ("noche 20-24", t.hod >= 20)]:
    g = t[m]; p, rc = pr(g.alarm, g.te)
    print(f"| {lab} | {p:.2f} | {rc:.2f} | {g.te.sum()} |")

fig, ax = plt.subplots(1, 2, figsize=(12, 5))
for name, c in [("q10", "#c0392b"), ("punto", "#888")]:
    ps, rs = zip(*curves[name])
    ax[0].plot(rs, ps, "o-", c=c, ms=3, label=f"umbral sobre {name}")
ax[0].scatter(*curves["q10"][best][::-1], s=120, facecolors="none", edgecolors="k", label=f"mejor F1 (θ={THETAS[best]:.2f})")
ax[0].set(xlabel="recall (vaciados cazados)", ylabel="precisión (alarmas acertadas)",
          title="Curva precision-recall de la alarma")
ax[0].legend(); ax[0].grid(alpha=.3)
seg = t.groupby("cluster").apply(lambda g: pd.Series(pr(g.alarm, g.te), index=["p", "r"]))
seg.plot.bar(ax=ax[1], color=["#c0392b", "#2b6cb0"])
ax[1].set(title=f"Por cluster de estación (θ={TH:.2f})", ylim=(0, 1))
ax[1].legend(["precisión", "recall"]); ax[1].grid(alpha=.3, axis="y")
fig.tight_layout(); fig.savefig("analysis/alarm_tuning.png", dpi=110)
