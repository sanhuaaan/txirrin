#!/usr/bin/env python3
"""Relieve para el timelapse: muestrea un modelo digital de elevación sobre la
caja de los barrios y lo guarda como rejilla en viz/donostia-dem.json.

Fuente: OpenTopoData, dataset EU-DEM 25 m. Gratuita, sin clave, 100 puntos
por petición y 1 petición/s (Open-Meteo elevation también vale, pero su
límite público salta hacia la petición 40 y bloquea un buen rato). Se ejecuta una vez; el resultado se
versiona y lo embebe build_timelapse.py en la página.

Misma convención que build_timelapse.py: metros locales, origen en el centro
del geo de barrios, y = norte. Paso de 100 m: algo más fino que el DEM, que
es lo que aguanta sin inventar detalle.
"""
import json, math, os, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEO = os.path.join(ROOT, "viz", "donostia-barrios.json")
OUT = os.path.join(ROOT, "viz", "donostia-dem.json")
M_DEG = 111320.0
STEP = 100            # m
MARGIN = 600          # m alrededor del bbox de barrios: que el mar y los montes
                      # no se corten a ras de límite municipal
API = "https://api.opentopodata.org/v1/eudem25m?locations={locs}"


def main():
    geo = json.load(open(GEO, encoding="utf-8"))
    lat0, lon0 = geo["center"]
    xs = [p[0] for r in geo["polys"] for p in r]
    ys = [p[1] for r in geo["polys"] for p in r]
    x0 = (min(xs) - MARGIN) // STEP * STEP
    y0 = (min(ys) - MARGIN) // STEP * STEP
    nx = int((max(xs) + MARGIN - x0) // STEP) + 1
    ny = int((max(ys) + MARGIN - y0) // STEP) + 1
    kx = M_DEG * math.cos(math.radians(lat0))
    pts = [(lat0 + (y0 + j * STEP) / M_DEG, lon0 + (x0 + i * STEP) / kx)
           for j in range(ny) for i in range(nx)]
    print(f"{nx}x{ny} = {len(pts)} puntos, {math.ceil(len(pts)/100)} peticiones", file=sys.stderr)
    z = []
    for k in range(0, len(pts), 100):
        chunk = pts[k:k + 100]
        url = API.format(locs="|".join(f"{p[0]:.5f},{p[1]:.5f}" for p in chunk))
        for attempt in range(5):
            try:
                with urllib.request.urlopen(url, timeout=30) as r:
                    z.extend((q["elevation"] or 0) for q in json.load(r)["results"]); break
            except Exception as e:
                if attempt == 4: raise
                time.sleep(15 if getattr(e, "code", 0) == 429 else 2 * (attempt + 1))
        time.sleep(1.1)   # el límite es 1 petición/s
    z = [max(0, int(round(v))) for v in z]   # el mar sale 0 o negativo: todo 0
    dem = {"note": "EU-DEM 25 m via OpenTopoData; metros locales, y=norte; "
                   "z en metros, 0 = mar; filas de sur a norte",
           "x0": int(x0), "y0": int(y0), "step": STEP, "nx": nx, "ny": ny, "z": z}
    json.dump(dem, open(OUT, "w"), separators=(",", ":"))
    print(f"{OUT}: max {max(z)} m, {sum(1 for v in z if v == 0)} celdas de mar", file=sys.stderr)


if __name__ == "__main__":
    main()
