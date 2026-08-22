#!/usr/bin/env python3
"""El Urumea para el timelapse, desde OpenStreetMap (Overpass).

A 50 m por celda un río de 30-60 m de ancho no cabe en el relieve: se promedia
con las orillas y desaparece. Así que va como vector: el eje (waterway=river)
como polilíneas y la lámina de agua de la ría (natural=water) como polígono,
en metros locales con el mismo origen que todo lo demás. Se guarda en
viz/donostia-dem.json como `rivers` y `water`. Se ejecuta una vez. (Las
playas se probaron y se quitaron: no aportaban y ensuciaban.)
"""
import json, math, os, sys, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEO = os.path.join(ROOT, "viz", "donostia-barrios.json")
DEM = os.path.join(ROOT, "viz", "donostia-dem.json")
M_DEG = 111320.0
Q = ('[out:json][timeout:50];('
     'way["waterway"="river"]["name"~"Urumea"]({b});'
     'way["natural"="water"]["water"="river"]["name"~"Urumea"]({b}););out geom;')


def dp(pts, tol):                       # Douglas-Peucker
    if len(pts) < 3: return pts
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    dx, dy = x2 - x1, y2 - y1; n = math.hypot(dx, dy) or 1
    i, dmax = max(((i, abs((p[0]-x1)*dy - (p[1]-y1)*dx) / n) for i, p in enumerate(pts[1:-1], 1)), key=lambda t: t[1])
    if dmax <= tol: return [pts[0], pts[-1]]
    return dp(pts[:i+1], tol)[:-1] + dp(pts[i:], tol)


def main():
    geo = json.load(open(GEO, encoding="utf-8")); lat0, lon0 = geo["center"]
    d = json.load(open(DEM)); x0, y0, st = d["x0"], d["y0"], d["step"]
    x1, y1 = x0 + (d["nx"] - 1) * st, y0 + (d["ny"] - 1) * st
    kx = M_DEG * math.cos(math.radians(lat0))
    bbox = f"{lat0 + y0/M_DEG:.5f},{lon0 + x0/kx:.5f},{lat0 + y1/M_DEG:.5f},{lon0 + x1/kx:.5f}"
    url = "https://overpass-api.de/api/interpreter?data=" + urllib.parse.quote(Q.format(b=bbox))
    req = urllib.request.Request(url, headers={"User-Agent": "dbizi-timelapse (github sanhuaaan)"})
    with urllib.request.urlopen(req, timeout=90) as r: els = json.load(r)["elements"]
    loc = lambda g: (round((g["lon"] - lon0) * kx), round((g["lat"] - lat0) * M_DEG))
    inside = lambda p: x0 <= p[0] <= x1 and y0 <= p[1] <= y1
    rivers, water = [], []
    def ring(pts, tol):                 # anillo cerrado: DP necesita dos mitades
        r = [p for p in pts if inside(p)]; m = len(r) // 2
        return dp(r[:m + 1], tol)[:-1] + dp(r[m:], tol) if len(r) > 3 else None
    for w in els:
        pts = [loc(g) for g in w["geometry"]]
        if w["tags"].get("waterway") == "river":
            run = []                      # se parte donde sale de la maqueta
            for p in pts:
                if inside(p): run.append(p)
                elif len(run) > 1: rivers.append(dp(run, 12)); run = []
                else: run = []
            if len(run) > 1: rivers.append(dp(run, 12))
        else:
            water.append(ring(pts, 10))
    d.pop("beaches", None)
    d["rivers"], d["water"] = rivers, water
    d["note"] = d["note"].split("; rivers")[0] + "; rivers/water: Urumea desde OSM (scripts/fetch_river.py)"
    json.dump(d, open(DEM, "w"), separators=(",", ":"))
    print(f"{len(rivers)} tramos ({sum(len(r) for r in rivers)} pts), {len(water)} láminas "
          f"({sum(len(w) for w in water)} pts)", file=sys.stderr)


if __name__ == "__main__":
    main()
