"""Perfil 24 h por estación y clustering k-means.

Entrada: data/profiles.csv (agregado horario exportado de la VM, ver sql/profiles.sql).
Salida:  data/profiles_clusters.csv + analysis/profiles.png

    python3 analysis/profiles.py [k]
"""
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

K = int(sys.argv[1]) if len(sys.argv) > 1 else 4
FLAT = 0.7  # ponytail: >70 % del tiempo vacía o llena = curva plana, se aparta del clustering

df = pd.read_csv("data/profiles.csv")
occ = df.pivot_table(index="station_id", columns=["daytype", "hour"], values="occ").interpolate(axis=1)
occ = occ.reindex(columns=pd.MultiIndex.from_product([["weekday", "weekend"], range(24)])).ffill(axis=1).bfill(axis=1)
meta = df.groupby("station_id").agg(name=("name", "first"), lat=("lat", "first"), lon=("lon", "first"),
                                     p_empty=("p_empty", "mean"), p_full=("p_full", "mean"),
                                     occ_mean=("occ", "mean")).loc[occ.index]

flat = (meta.p_empty > FLAT) | (meta.p_full > FLAT)
X = occ[~flat].to_numpy()
X = X - X.mean(axis=1, keepdims=True)  # forma, no nivel


def kmeans(X, k, restarts=20, iters=100, seed=0):
    rng = np.random.default_rng(seed)
    best = None
    for _ in range(restarts):
        C = X[rng.choice(len(X), k, replace=False)]
        for _ in range(iters):
            lab = np.argmin(((X[:, None, :] - C[None]) ** 2).sum(-1), axis=1)
            newC = np.array([X[lab == j].mean(0) if (lab == j).any() else C[j] for j in range(k)])
            if np.allclose(newC, C):
                break
            C = newC
        inertia = ((X - C[lab]) ** 2).sum()
        if best is None or inertia < best[0]:
            best = (inertia, lab, C)
    return best[1], best[2]


lab, C = kmeans(X, K)
# etiquetas estables: ordenar clústeres por hora del mínimo laborable (residencial se vacía antes)
order = np.argsort([np.argmin(c[:24]) for c in C])
remap = {old: new for new, old in enumerate(order)}
lab = np.array([remap[l] for l in lab])
C = C[order]

meta["cluster"] = -1
meta.loc[~flat, "cluster"] = lab
meta.to_csv("data/profiles_clusters.csv")

fig, axes = plt.subplots(2, K + 1, figsize=(4 * (K + 1), 7))
colors = plt.cm.tab10(np.arange(K))
for j in range(K):
    for row, dt in enumerate(["weekday", "weekend"]):
        ax = axes[row, j]
        sl = slice(0, 24) if dt == "weekday" else slice(24, 48)
        for x in X[lab == j]:
            ax.plot(range(24), x[sl], color=colors[j], alpha=0.25)
        ax.plot(range(24), C[j][sl], color="k", lw=2)
        ax.set_ylim(-0.5, 0.5); ax.axhline(0, color="grey", lw=0.5)
        ax.set_title(f"C{j} {dt} (n={int((lab == j).sum())})")
        ax.set_xticks(range(0, 24, 6))
gs = axes[0, K].get_gridspec()
for ax in axes[:, K]:
    ax.remove()
axm = fig.add_subplot(gs[:, K])
for j in range(K):
    m = meta[meta.cluster == j]
    axm.scatter(m.lon, m.lat, color=colors[j], label=f"C{j}", s=40)
m = meta[flat]
axm.scatter(m.lon, m.lat, color="lightgrey", marker="x", label="plana", s=40)
axm.set_aspect(1 / np.cos(np.radians(43.3))); axm.legend(); axm.set_title("mapa")
fig.suptitle(f"Ocupación normalizada (media restada), k={K}, {df.n.sum():,} snapshots")
fig.tight_layout(); fig.savefig("analysis/profiles.png", dpi=110)

for j in range(K):
    c = C[j]
    print(f"\nC{j}: min laborable {np.argmin(c[:24])}h  max laborable {np.argmax(c[:24])}h  "
          f"amplitud finde {c[24:].ptp():.2f}")
    print("  " + ", ".join(meta[meta.cluster == j].name.str.replace(r"^\d+ - ", "", regex=True)))
print("\nPlanas:", ", ".join(meta[flat].name), f"(p_empty>{FLAT} o p_full>{FLAT})")
