"""Rutinas semanales de la red: excesos locales recurrentes por día × franja.

Generaliza el detector del pintxo-pote: 7 días × 4 franjas × llegadas/salidas,
deflactando el factor global de red de cada día (si toda la red sube el
viernes, eso no es una rutina local). Exceso >=1.5x sobre el resto de días,
repetido en >=80 % de las semanas, con volumen mínimo.

Entrada: data/events.csv.gz + data/profiles.csv
Salida:  markdown por stdout

    python3 analysis/weekly_flows.py > analysis/weekly_flows.md
"""
import numpy as np
import pandas as pd

MIN_VOL, MIN_RATIO, MIN_HITS = 8, 1.5, 0.8
PARTS = {"mañana 7-11": (7, 11), "mediodía 11-15": (11, 15), "tarde 15-19": (15, 19), "noche 19-23": (19, 23)}
DOWS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

ev = pd.read_csv("data/events.csv.gz", parse_dates=["ts"])
ev["ts"] = ev.ts.dt.tz_convert("Europe/Madrid")
ev["dow"], ev["date"], ev["h"] = ev.ts.dt.dayofweek, ev.ts.dt.date, ev.ts.dt.hour
st = pd.read_csv("data/profiles.csv").groupby("station_id")[["name"]].first()

out = []
for pname, (h0, h1) in PARTS.items():
    e = ev[(ev.h >= h0) & (ev.h < h1)]
    for col in ["arr", "dep"]:
        day = e.groupby(["station_id", "date", "dow"])[col].sum().reset_index()
        dates = e[["date", "dow"]].drop_duplicates()
        full = (day.set_index(["station_id", "date"])
                  .reindex(pd.MultiIndex.from_product([st.index, dates.date], names=["station_id", "date"]))
                  [col].fillna(0).reset_index().merge(dates, on="date"))
        netf = full.groupby("dow")[col].mean()
        netf = netf / netf.mean()
        for sid, g in full.groupby("station_id"):
            m = g.groupby("dow")[col].mean() / netf
            if len(m) < 7:
                continue
            for d in range(7):
                rest = m.drop(d).mean()
                if m[d] >= MIN_VOL and rest > 0 and m[d] / rest >= MIN_RATIO:
                    hits = (g[g.dow == d][col] / netf[d] > rest).mean()
                    if hits >= MIN_HITS:
                        out.append((st.loc[sid, "name"], DOWS[d], pname,
                                    "llegadas" if col == "arr" else "salidas",
                                    m[d], rest, m[d] / rest, hits))

r = pd.DataFrame(out, columns=["estación", "día", "franja", "tipo", "vol", "resto", "exceso", "consistencia"])
r = r.sort_values("exceso", ascending=False)
nsem = ev.date.nunique() // 7
print(f"# Rutinas semanales de la red ({ev.date.nunique()} días, ~{nsem} ocurrencias por día de la semana)\n")
print("Exceso local (deflactado del factor de red del día) >=1.5x, repetido en >=80 % de las semanas.\n")
print("| estación | día | franja | tipo | por día | resto | exceso | consistencia |")
print("|---|---|---|---|---|---|---|---|")
for _, x in r.head(25).iterrows():
    print(f"| {x['estación']} | **{x['día']}** | {x.franja} | {x.tipo} | {x.vol:.0f} | {x.resto:.0f} "
          f"| ×{x.exceso:.1f} | {x.consistencia*100:.0f} % |")
