"""Informe de nivel de servicio por estación a partir de data/profiles.csv.

    python3 analysis/service_level.py > analysis/service_level.md
"""
import pandas as pd

df = pd.read_csv("data/profiles.csv")
df["name"] = df.name.str.replace(r"^\d+\s*[-–]\s*", "", regex=True)
w = df.n  # media ponderada por snapshots
def wavg(g, col): return (g[col] * g.n).sum() / g.n.sum()

st = df.groupby("name").apply(lambda g: pd.Series({
    "vacia": wavg(g, "p_empty"), "llena": wavg(g, "p_full"),
    "sin_elec": wavg(g, "p_no_elec"), "sin_mech": wavg(g, "p_no_mech"),
    "peor_hora_vacia": g.loc[g.p_empty.idxmax(), "hour"], "peor_vacia": g.p_empty.max(),
    "peor_hora_llena": g.loc[g.p_full.idxmax(), "hour"], "peor_llena": g.p_full.max()}))
st["sin_servicio"] = st.vacia + st.llena

hours = df[df.daytype == "weekday"].groupby("hour").apply(lambda g: pd.Series({
    "vacia": wavg(g, "p_empty"), "llena": wavg(g, "p_full"), "sin_elec": wavg(g, "p_no_elec")}))

pct = lambda x: f"{100*x:.0f} %"
print(f"# Nivel de servicio Dbizi\n\nDatos: {df.n.sum():,} snapshots (cada 2 min), {df.name.nunique()} estaciones. "
      "Cifras = % del tiempo. *Vacía* = 0 bicis (no puedes coger); *llena* = 0 anclajes (no puedes dejar); "
      "*sin eléctrica* = hay mecánicas pero ninguna eléctrica.\n")
print(f"## Red\n\n- Tiempo medio con estación vacía: **{pct(st.vacia.mean())}** · llena: **{pct(st.llena.mean())}** "
      f"· sin eléctricas (habiendo mecánicas): **{pct(st.sin_elec.mean())}** · sin mecánicas (habiendo eléctricas): {pct(st.sin_mech.mean())}")
print(f"- Estaciones sin servicio (vacía o llena) más del 25 % del tiempo: **{(st.sin_servicio > .25).sum()}**; más del 50 %: **{(st.sin_servicio > .5).sum()}**\n")

def table(s, cols, title):
    print(f"## {title}\n\n| Estación | " + " | ".join(cols.values()) + " |\n|---|" + "---|" * len(cols))
    for name, r in s.iterrows():
        print(f"| {name} | " + " | ".join(pct(r[c]) if not c.startswith("peor_hora") else f"{int(r[c])} h" for c in cols) + " |")
    print()

table(st.sort_values("vacia", ascending=False).head(10), {"vacia": "vacía", "peor_hora_vacia": "peor hora", "peor_vacia": "vacía a esa hora"}, "Top 10 estaciones vacías")
table(st.sort_values("llena", ascending=False).head(10), {"llena": "llena", "peor_hora_llena": "peor hora", "peor_llena": "llena a esa hora"}, "Top 10 estaciones llenas")
table(st.sort_values("sin_elec", ascending=False).head(10), {"sin_elec": "sin eléctrica", "vacia": "vacía"}, "Top 10 estaciones sin eléctricas")

print("## Perfil horario de la red (laborable)\n\n| Hora | vacía | llena | sin eléctrica |\n|---|---|---|---|")
for h, r in hours.iterrows():
    print(f"| {h:02d} | {pct(r.vacia)} | {pct(r.llena)} | {pct(r.sin_elec)} |")
