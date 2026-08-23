#!/usr/bin/env python3
"""Cobertura del suelo y viales principales para el timelapse, desde OSM.

El relieve solo sabía de altura; la ciudad, los parques y los montes de bosque
se pintaban igual. Aquí se bajan los polígonos de OSM con una clase (1 hierba/
parque/cultivo, 2 bosque/matorral, 3 urbano), se simplifican y se guardan como
vectores `cover` ([clase, anillo]) en viz/donostia-dem.json, junto con los
viales (motorway/trunk/primary) como polilíneas `roads`, en metros locales.
(Se probó rasterizar por celda del DEM y salía a bloques, el mismo defecto que
el pixel art que se descartó.) Se ejecuta una vez.
"""
import json, math, os, sys, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEO = os.path.join(ROOT, "viz", "donostia-barrios.json")
DEM = os.path.join(ROOT, "viz", "donostia-dem.json")
M_DEG = 111320.0
Q = ('[out:json][timeout:120];('
     'wr["landuse"~"^(residential|industrial|commercial|retail|railway|'
     'grass|meadow|farmland|orchard|cemetery|recreation_ground|forest)$"]({b});'
     'wr["natural"~"^(wood|scrub|heath|grassland)$"]({b});'
     'wr["leisure"~"^(park|garden|pitch|golf_course)$"]({b});'
     'way["highway"~"^(motorway|trunk|primary)$"]({b}););out geom;')
URBAN = {"residential", "industrial", "commercial", "retail", "railway"}
GREEN = {"grass", "meadow", "farmland", "orchard", "cemetery", "recreation_ground",
         "grassland", "park", "garden", "pitch", "golf_course"}
WOOD = {"forest", "wood", "scrub", "heath"}
TOL = 18                                  # m, Douglas-Peucker
MIN_AREA = {1: 4000, 2: 10000, 3: 10000}  # m2: no vale la pena pintarlo


def dp(pts, tol):
    if len(pts) < 3: return pts
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    dx, dy = x2 - x1, y2 - y1; n = math.hypot(dx, dy) or 1
    i, dmax = max(((i, abs((p[0]-x1)*dy - (p[1]-y1)*dx) / n) for i, p in enumerate(pts[1:-1], 1)), key=lambda t: t[1])
    if dmax <= tol: return [pts[0], pts[-1]]
    return dp(pts[:i+1], tol)[:-1] + dp(pts[i:], tol)


def clip(r, x0, y0, x1, y1):            # Sutherland-Hodgman al rectángulo de la maqueta
    for ins, cut in ((lambda p: p[0] >= x0, lambda a, b: (x0, a[1] + (b[1]-a[1]) * (x0-a[0]) / (b[0]-a[0]))),
                     (lambda p: p[0] <= x1, lambda a, b: (x1, a[1] + (b[1]-a[1]) * (x1-a[0]) / (b[0]-a[0]))),
                     (lambda p: p[1] >= y0, lambda a, b: (a[0] + (b[0]-a[0]) * (y0-a[1]) / (b[1]-a[1]), y0)),
                     (lambda p: p[1] <= y1, lambda a, b: (a[0] + (b[0]-a[0]) * (y1-a[1]) / (b[1]-a[1]), y1))):
        out = []
        for i, b in enumerate(r):
            a = r[i - 1]
            if ins(b):
                if not ins(a): out.append(cut(a, b))
                out.append(b)
            elif ins(a): out.append(cut(a, b))
        r = out
        if not r: break
    return r


def main():
    geo = json.load(open(GEO, encoding="utf-8")); lat0, lon0 = geo["center"]
    d = json.load(open(DEM)); x0, y0, st, nx, ny = d["x0"], d["y0"], d["step"], d["nx"], d["ny"]
    x1, y1 = x0 + (nx - 1) * st, y0 + (ny - 1) * st
    kx = M_DEG * math.cos(math.radians(lat0))
    bbox = f"{lat0 + y0/M_DEG:.5f},{lon0 + x0/kx:.5f},{lat0 + y1/M_DEG:.5f},{lon0 + x1/kx:.5f}"
    url = "https://overpass-api.de/api/interpreter?data=" + urllib.parse.quote(Q.format(b=bbox))
    req = urllib.request.Request(url, headers={"User-Agent": "txirrin (github sanhuaaan)"})
    with urllib.request.urlopen(req, timeout=180) as r: els = json.load(r)["elements"]
    loc = lambda g: ((g["lon"] - lon0) * kx, (g["lat"] - lat0) * M_DEG)
    cell = lambda p: ((p[0] - x0) / st, (p[1] - y0) / st)      # coordenadas de celda
    CW, CH = nx - 1, ny - 1
    layers = {1: [], 2: [], 3: []}
    roads = []
    def klass(t):
        v = t.get("landuse") or t.get("natural") or t.get("leisure")
        return 3 if v in URBAN else 2 if v in WOOD else 1 if v in GREEN else 0
    def rings(e):
        if e["type"] == "way": return [[loc(g) for g in e["geometry"]]]
        return [[loc(g) for g in m["geometry"]] for m in e.get("members", [])
                if m.get("role") in ("outer", "") and "geometry" in m]
    inside = lambda p: x0 <= p[0] <= x1 and y0 <= p[1] <= y1
    for e in els:
        t = e.get("tags", {})
        if "highway" in t:
            pts = [(round(x), round(y)) for x, y in (loc(g) for g in e["geometry"])]
            run = []
            for p in pts:
                if inside(p): run.append(p)
                elif len(run) > 1: roads.append(dp(run, 15)); run = []
                else: run = []
            if len(run) > 1: roads.append(dp(run, 15))
            continue
        k = klass(t)
        if k: layers[k].extend(rings(e))
    # simplificar y quitar lo diminuto: el peso del json manda. Orden de pintado:
    # urbano, parques encima, bosque el último (gana en el monte y un parque
    # dentro del barrio se ve)
    def area(r): return abs(sum(r[i][0]*r[(i+1)%len(r)][1] - r[(i+1)%len(r)][0]*r[i][1] for i in range(len(r)))) / 2
    cover = []
    for k in (3, 1, 2):
        for r in layers[k]:
            r = [(round(x), round(y)) for x, y in clip(r, x0, y0, x1, y1)]
            if len(r) < 4 or area(r) < MIN_AREA[k]: continue
            m = len(r) // 2
            rr = dp(r[:m + 1], TOL)[:-1] + dp(r[m:], TOL)
            if len(rr) >= 3: cover.append([k, [list(p) for p in rr]])
    d.pop("lc", None)
    d["cover"], d["roads"] = cover, roads
    d["note"] = d["note"].split("; lc/roads")[0].split("; cover/roads")[0] + "; cover/roads: cobertura del suelo y viales desde OSM (scripts/fetch_landcover.py)"
    json.dump(d, open(DEM, "w"), separators=(",", ":"))
    print(f"{len(els)} elementos; polígonos: " + ", ".join(f"{k}={sum(1 for c in cover if c[0]==k)}" for k in (1,2,3))
          + f" ({sum(len(c[1]) for c in cover)} pts); {len(roads)} tramos de vial ({sum(len(r) for r in roads)} pts)", file=sys.stderr)


if __name__ == "__main__":
    main()
