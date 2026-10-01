"""Backtest zero-shot: TimesFM 3.0 vs baselines sobre bicis por estación a 15 min.

Entrada: data/forecast_series.csv (sql/forecast_series.sql)
Salida:  data/forecast_eval_raw.csv.gz (una fila por origen x estación x paso x modelo)
         y resumen markdown por stdout.

    .venv/bin/python analysis/forecast_eval.py [--every 2] [--limit N] > analysis/forecast_eval.md

Corre en CPU (~28 s por origen con 70 estaciones); el run completo son ~2 h.
"""
import argparse
import numpy as np
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--every", type=int, default=2, help="horas entre orígenes")
ap.add_argument("--limit", type=int, default=0, help="máx. orígenes (0 = todos)")
ap.add_argument("--ctx", type=int, default=512, help="puntos de contexto")
a = ap.parse_args()

H = 8                          # horizonte 2 h
CTX = a.ctx
STEPS = {"30min": 2, "1h": 4, "2h": 8}
EMPTY = 0.5                     # <= media bici: vacía

df = pd.read_csv("data/forecast_series.csv", parse_dates=["ts"])
cap = df.groupby("station_id").capacity.max()
wide = df.pivot(index="ts", columns="station_id", values="bikes")
wide = wide.reindex(pd.date_range(wide.index.min(), wide.index.max(), freq="15min"))
wide = wide.interpolate(limit=4, limit_area="inside")   # huecos de hasta 1 h

idx_local = wide.index.tz_localize("UTC").tz_convert("Europe/Madrid")
# orígenes: semanas lectivas, cada N horas en punto
origins = [i for i, t in enumerate(idx_local)
           if t.minute == 0 and t.hour % a.every == 0
           and pd.Timestamp("2026-09-08", tz="Europe/Madrid") <= t < pd.Timestamp("2026-10-01", tz="Europe/Madrid")]
if a.limit:
    origins = origins[:a.limit]

import torch, timesfm
torch.set_num_threads(4)
model = timesfm.TimesFM3Forecaster.from_pretrained("google/timesfm-3.0-pytorch", device="cpu")

V = wide.to_numpy()
rows = []
for n, o in enumerate(origins):
    if o < CTX + 7 * 96 or o + H >= len(V):
        continue
    ctx, truth = V[o - CTX + 1:o + 1], V[o + 1:o + 1 + H]
    ok = ~np.isnan(ctx).any(0) & ~np.isnan(truth).any(0)
    sids = wide.columns[ok]
    if not len(sids):
        continue
    c = cap[sids].to_numpy()
    out = list(model.predict_batch([ctx[:, j].astype(np.float32) for j in np.where(ok)[0]],
                                   horizon=H, return_quantiles=True, make_positive=True))
    tfm = np.clip(np.stack([x.forecast for x in out], 1), 0, c)          # (H, S)
    q10 = np.clip(np.stack([x.quantiles[:, 0] for x in out], 1), 0, c)
    q90 = np.clip(np.stack([x.quantiles[:, 8] for x in out], 1), 0, c)
    last = ctx[-1, ok]
    pers = np.tile(last, (H, 1))
    naive = V[o + 1 - 96:o + 1 + H - 96][:, ok]                          # mismo cuarto de hora ayer
    prof = np.nanmean(np.stack([V[o + 1 - k * 96:o + 1 + H - k * 96][:, ok] for k in range(1, 8)]), 0)
    prof0 = np.nanmean(np.stack([V[o - k * 96, ok] for k in range(1, 8)]), 0)
    blend = prof + (last - prof0) * (0.9 ** np.arange(1, H + 1))[:, None]  # perfil + persistencia que decae
    t0 = wide.index[o]
    for name, pred in [("timesfm", tfm), ("persistence", pers), ("naive24h", naive), ("profile", blend)]:
        for lab, h in STEPS.items():
            for j, sid in enumerate(sids):
                rows.append((t0, sid, name, lab, pred[h - 1, j], truth[h - 1, j], last[j],
                             q10[h - 1, j] if name == "timesfm" else np.nan,
                             q90[h - 1, j] if name == "timesfm" else np.nan))
    if n % 10 == 0:
        print(f"# {n+1}/{len(origins)} orígenes", flush=True)

r = pd.DataFrame(rows, columns=["t0", "station_id", "model", "h", "pred", "truth", "last", "q10", "q90"])
r.to_csv("data/forecast_eval_raw.csv.gz", index=False)

print(f"\n# Backtest zero-shot ({r.t0.nunique()} orígenes cada {a.every} h, "
      f"{r.station_id.nunique()} estaciones, semanas lectivas sep-2026)\n")
r["ae"] = (r.pred - r.truth).abs()
mae = r.pivot_table(index="model", columns="h", values="ae").reindex(columns=list(STEPS))
print("## MAE (bicis)\n")
print(mae.round(2).to_markdown())
tf = r[r.model == "timesfm"]
cov = tf.assign(inb=(tf.truth >= tf.q10) & (tf.truth <= tf.q90)).pivot_table(index="model", columns="h", values="inb")
print("\n## Cobertura banda p10-p90 (objetivo 0.80)\n")
print(cov.reindex(columns=list(STEPS)).round(2).to_markdown())
print("\n## 'Vacía en 30 min' (verdad: <=0.5 bicis; predicción: pred <=0.5)\n")
e = r[r.h == "30min"].copy()
e["pe"], e["te"] = e.pred <= EMPTY, e.truth <= EMPTY
print("| modelo | precisión | recall | precisión (transiciones) | recall (transiciones) |")
print("|---|---|---|---|---|")
for m, g in e.groupby("model"):
    tr = g[g.last > EMPTY]      # la estación NO estaba vacía en el origen
    def pr(g):
        p = (g.pe & g.te).sum() / max(1, g.pe.sum()); rc = (g.pe & g.te).sum() / max(1, g.te.sum())
        return p, rc
    p1, r1 = pr(g); p2, r2 = pr(tr)
    print(f"| {m} | {p1:.2f} | {r1:.2f} | {p2:.2f} | {r2:.2f} |")
print("\n(transiciones: estaciones que no estaban vacías en el origen; ahí la persistencia no puede acertar.)")
