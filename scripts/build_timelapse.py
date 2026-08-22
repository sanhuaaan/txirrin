#!/usr/bin/env python3
"""Genera viz/timelapse.html: el timelapse isométrico de la red Dbizi.

Sin dependencias (solo stdlib): come dos CSV y escribe un HTML autocontenido.
La geometría de los barrios ya viene simplificada y recortada en
viz/donostia-barrios.json, así que el build no depende de que donostia.eus responda.

Exportar los CSV desde la VM:

  . ~/.dbizi.env
  Q() { sudo docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" dbizi-postgres-1 \
        psql -U dbizi -d dbizi -tAF, -c "$1"; }
  Q "SELECT station_id, name, ST_Y(geom), ST_X(geom), capacity
     FROM dbizi_station ORDER BY station_id;" > stations.csv
  Q "SELECT station_id, to_char(ts AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS'),
            bikes_available
     FROM dbizi_measurement WHERE ts >= '2026-08-20' ORDER BY ts, station_id;" > meas.csv

Uso:  ./build_timelapse.py stations.csv meas.csv [--minutes 5] [--out viz/timelapse.html]

Acotar el WHERE de la segunda consulta es lo que permite la versión que de verdad
interesa: dos días comparables (lunes lluvioso vs. lunes seco) en vez de todo el
histórico de una vez.
"""
import argparse
import csv
import html
import re
import json
import math
import os
import sys
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M_DEG = 111320.0


def load_stations(path, center=None):
    st = []
    for r in csv.reader(open(path, encoding="utf-8")):
        if len(r) < 5 or not r[0].strip():
            continue
        st.append(dict(id=r[0], n=r[1].strip(), lat=float(r[2]), lon=float(r[3]),
                       c=int(r[4] or 0)))
    if not st:
        sys.exit(f"{path}: sin estaciones")
    st.sort(key=lambda s: s["id"])
    lat0, lon0 = center or (sum(s["lat"] for s in st) / len(st),
                            sum(s["lon"] for s in st) / len(st))
    for s in st:
        s["x"] = round((s["lon"] - lon0) * M_DEG * math.cos(math.radians(lat0)))
        s["y"] = round((s["lat"] - lat0) * M_DEG)
    return st, (lat0, lon0)


def build_frames(path, st, minutes):
    """Rejilla regular tomando el último snapshot anterior a cada marca.

    La cadencia real es irregular (5 min del scraping inicial, 2 min del collector
    directo), y una animación necesita paso constante para no dar tirones.
    """
    idx = {s["id"]: i for i, s in enumerate(st)}
    snaps = {}
    for r in csv.reader(open(path, encoding="utf-8")):
        if len(r) < 3 or r[0] not in idx or not r[2].strip():
            continue
        snaps.setdefault(r[1], {})[idx[r[0]]] = int(r[2])
    if not snaps:
        sys.exit(f"{path}: sin mediciones")
    keys = sorted(snaps)
    ordered = [(datetime.fromisoformat(k), k) for k in keys]
    t, end = ordered[0][0].replace(second=0, microsecond=0), ordered[-1][0]
    frames, j, last = [], 0, None
    while t <= end:
        while j < len(ordered) and ordered[j][0] <= t:
            last = ordered[j][1]
            j += 1
        if last is not None:
            m = snaps[last]
            frames.append({"t": t.strftime("%Y-%m-%dT%H:%M"),
                           "b": [m.get(i, 0) for i in range(len(st))]})
        t += timedelta(minutes=minutes)
    return frames


HORA = re.compile(r"(?<!\d)([01]?\d|2[0-3])[:.]([0-5]\d)(?!\d)|(?:a\s+las|a\s+partir\s+de\s+las)\s+([01]?\d|2[0-3])\s*(?:h\b|horas)", re.I)


def hora_de(e):
    """Kulturklik no publica hora de comienzo (startDate va a las 00:00): se
    rescata de la descripción cuando la menciona de forma clara. Si no, None."""
    txt = html.unescape(re.sub(r"<[^>]+>", " ", (e.get("descriptionEs") or "") + " " + (e.get("nameEs") or "")))
    for m in HORA.finditer(txt):
        h = int(m.group(1) or m.group(3)); mi = int(m.group(2) or 0)
        if 7 <= h <= 23: return f"{h:02d}:{mi:02d}"
    return None


def load_context(weather, holidays, events, frames):
    """Lo que rodea a la marea: meteo horaria, tipo de día y eventos. Todo es
    opcional; la página funciona sin nada de esto."""
    ctx = {}
    if weather and os.path.exists(weather):
        w = []
        for r in csv.reader(open(weather, encoding="utf-8")):
            if len(r) < 4 or not r[0].strip(): continue
            num = lambda v: None if v == "" else round(float(v), 1)
            w.append({"t": r[0], "temp": num(r[1]), "mm": num(r[2]), "wind": num(r[3])})
        ctx["weather"] = w
    days = sorted({f["t"][:10] for f in frames})
    if holidays and os.path.exists(holidays):
        hol = {r[0]: r[1] for r in csv.reader(open(holidays, encoding="utf-8")) if len(r) >= 2}
        ctx["holidays"] = {d: hol[d] for d in days if d in hol}
    if events and os.path.exists(events):
        import gzip
        with gzip.open(events, "rt", encoding="utf-8") as f:
            ev = [e for m in json.load(f)["months"].values() for e in m]
        out = {}
        for d in days:
            hoy = [e for e in ev if e["startDate"][:10] <= d <= e["endDate"][:10]]
            # lo de semanas (exposiciones, ciclos) no mueve bicis un día concreto
            cortos = [e for e in hoy if (datetime.fromisoformat(e["endDate"][:10])
                                         - datetime.fromisoformat(e["startDate"][:10])).days <= 2]
            counts = {}
            for e in cortos: counts[e.get("typeEs") or "Otro"] = counts.get(e.get("typeEs") or "Otro", 0) + 1
            items = sorted(({"type": e.get("typeEs") or "", "name": e["nameEs"].strip('"')[:90],
                             "place": (e.get("establishmentEs") or "")[:50], "h": hora_de(e)} for e in cortos),
                           key=lambda e: (e["h"] or "99", e["type"], e["name"]))
            out[d] = {"n": len(cortos), "counts": dict(sorted(counts.items(), key=lambda kv: -kv[1])[:4]), "items": items}
        ctx["events"] = out
    return ctx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stations"); ap.add_argument("measurements")
    ap.add_argument("--minutes", type=int, default=5, help="paso de la rejilla (def. 5)")
    ap.add_argument("--out", default=os.path.join(ROOT, "viz", "timelapse.html"))
    ap.add_argument("--geo", default=os.path.join(ROOT, "viz", "donostia-barrios.json"),
                    help="geometría de barrios (en la VM los ficheros van planos)")
    ap.add_argument("--tpl", default=os.path.join(ROOT, "viz", "timelapse.tpl.html"))
    ap.add_argument("--dem", default=os.path.join(ROOT, "viz", "donostia-dem.json"),
                    help="relieve (rejilla de scripts/fetch_dem.py); va dentro del HTML, no del JSON")
    ap.add_argument("--json-only", metavar="RUTA",
                    help="escribe solo el JSON de datos, sin HTML (para la web viva)")
    ap.add_argument("--src", default="",
                    help="si se indica, el HTML NO lleva los datos dentro: los pide a esta ruta")
    ap.add_argument("--refresh", type=int, default=0,
                    help="segundos entre refrescos cuando se usa --src (0 = ninguno)")
    ap.add_argument("--weather", help="CSV ts,temp,mm,viento (horario) de la ventana; opcional")
    ap.add_argument("--holidays", help="CSV fecha,nombre; opcional")
    ap.add_argument("--events", help="cosecha de eventos (events_YYYYMMDD.json.gz); opcional")
    a = ap.parse_args()

    geo = json.load(open(a.geo, encoding="utf-8"))
    # mismo centro que la geometría, o los barrios saldrían desplazados
    st, center = load_stations(a.stations, tuple(geo["center"]))
    frames = build_frames(a.measurements, st, a.minutes)

    data = {"center": list(center), "polys": geo["polys"],
            "stations": [{k: s[k] for k in ("id", "n", "x", "y", "c")} for s in st],
            "frames": frames,
            "context": load_context(a.weather, a.holidays, a.events, frames)}
    blob = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    span = (datetime.fromisoformat(frames[-1]["t"]) - datetime.fromisoformat(frames[0]["t"]))
    resumen = (f"{len(st)} estaciones, {len(frames)} frames de {a.minutes} min "
               f"({span.total_seconds()/3600:.0f} h)")

    if a.json_only:
        with open(a.json_only, "w", encoding="utf-8") as f:
            f.write(blob)
        print(f"{a.json_only}: {resumen}, {os.path.getsize(a.json_only)/1024:.0f} KB")
        return

    tpl = open(a.tpl, encoding="utf-8").read()
    for marca in ("__DATA__", "__SRC__", "__REFRESH__", "__DEM__"):
        if marca not in tpl:
            sys.exit(f"la plantilla no tiene el marcador {marca}")
    # el relieve es estático: se embebe en la página, así el JSON vivo sigue
    # llevando solo lo que cambia
    dem = open(a.dem, encoding="utf-8").read().strip()
    html = (tpl.replace("__DATA__", "null" if a.src else blob)
               .replace("__SRC__", a.src)
               .replace("__REFRESH__", str(a.refresh * 1000))
               .replace("__DEM__", dem))
    if os.path.dirname(a.out):
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(html)
    modo = f"datos desde {a.src} cada {a.refresh}s" if a.src else "datos embebidos"
    print(f"{a.out}: {resumen}, {os.path.getsize(a.out)/1024:.0f} KB — {modo}")


if __name__ == "__main__":
    main()
