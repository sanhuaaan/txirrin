#!/usr/bin/env python3
"""Máscara de mar para el timelapse, a partir de la ortofoto real (PNOA, IGN).

El DEM solo no basta: la vega del Urumea y media Amara están a cota 0, igual
que el mar. Aquí se pide al WMS del IGN la ortofoto del recuadro de la
rejilla, se reduce a un píxel por nodo y se marca como mar lo que está a cota
0, tiene pinta de agua Y está conectado al borde norte por inundación: así
entran la bahía, Santa Clara y la ría, y no los tejados del centro. Guarda
`seapolys` (contorno suavizado del mar) en viz/donostia-dem.json. Se ejecuta una vez; necesita
Pillow solo aquí.

(Se probó también colorear cada celda desde la ortofoto, como pixel art. Se
descartó: la textura bajo las columnas las hacía más difíciles de leer.)
"""
import io, json, math, os, sys, urllib.request
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEO = os.path.join(ROOT, "viz", "donostia-barrios.json")
DEM = os.path.join(ROOT, "viz", "donostia-dem.json")
M_DEG = 111320.0
PX_POR_CELDA = 4
WMS = ("https://www.ign.es/wms-inspire/pnoa-ma?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap"
       "&LAYERS=OI.OrthoimageCoverage&STYLES=&CRS=EPSG:4326&BBOX={s},{w},{n},{e}"
       "&WIDTH={W}&HEIGHT={H}&FORMAT=image/png")


def contorno(sea, nx, ny, x0, y0, st):
    """Contorno del mar como polígonos suaves. Pintar el mar celda a celda
    deja la costa en escalera; aquí se traza el borde de la unión de celdas
    (aristas sin vecino de mar), se encadena en anillos y se suaviza con
    Chaikin. Coordenadas en metros locales, celda = cuadrado del nodo."""
    h = st / 2
    idx = lambda i, j: j * nx + i
    es = lambda i, j: 0 <= i < nx and 0 <= j < ny and sea[idx(i, j)]
    aristas = {}                       # punto inicial -> punto final (orientación CCW)
    for j in range(ny):
        for i in range(nx):
            if not sea[idx(i, j)]: continue
            cx, cy = x0 + i * st, y0 + j * st
            a, b, c, d_ = (cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h)
            if not es(i, j - 1): aristas[a] = b   # sur
            if not es(i + 1, j): aristas[b] = c   # este
            if not es(i, j + 1): aristas[c] = d_  # norte
            if not es(i - 1, j): aristas[d_] = a  # oeste
    anillos = []
    while aristas:
        p0 = next(iter(aristas)); ring = [p0]; p = aristas.pop(p0)
        while p != p0 and p in aristas:
            ring.append(p); p = aristas.pop(p)
        if len(ring) >= 8: anillos.append(ring)
    out = []
    for r in anillos:
        for _ in range(3):             # Chaikin: cada vuelta redondea las esquinas
            q = []
            for k in range(len(r)):
                a, b = r[k], r[(k + 1) % len(r)]
                q.append((0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]))
                q.append((0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1]))
            r = q
        out.append([[round(p[0]), round(p[1])] for p in r[::2]])   # la mitad de puntos basta
    return out


def main():
    geo = json.load(open(GEO, encoding="utf-8")); lat0, lon0 = geo["center"]
    d = json.load(open(DEM)); x0, y0, st, nx, ny = d["x0"], d["y0"], d["step"], d["nx"], d["ny"]
    kx = M_DEG * math.cos(math.radians(lat0))
    # recuadro centrado en los nodos: medio paso a cada lado
    w = lon0 + (x0 - st / 2) / kx; e = lon0 + (x0 + (nx - .5) * st) / kx
    s = lat0 + (y0 - st / 2) / M_DEG; n = lat0 + (y0 + (ny - .5) * st) / M_DEG
    W, H = nx * PX_POR_CELDA, ny * PX_POR_CELDA
    url = WMS.format(s=f"{s:.6f}", w=f"{w:.6f}", n=f"{n:.6f}", e=f"{e:.6f}", W=W, H=H)
    print(f"PNOA {W}x{H} px", file=sys.stderr)
    with urllib.request.urlopen(url, timeout=120) as r: png = r.read()
    im = Image.open(io.BytesIO(png)).convert("RGB")
    # media por bloque = reducir la imagen a un píxel por nodo
    small = im.resize((nx, ny), Image.BOX)
    px = small.load()
    z = d["z"]; cols = [None] * (nx * ny)
    for j in range(ny):            # la imagen va de norte a sur; la rejilla de sur a norte
        for i in range(nx):
            cols[j * nx + i] = px[i, ny - 1 - j]
    # Mar: cota 0 y pinta de agua (en el PNOA el mar es verde oscuro, no azul,
    # y el asfalto se le parece), pero solo lo CONECTADO al borde norte por
    # inundación. Así entran la bahía y las rías y no los tejados del centro.
    def agua(c):
        r_, g_, b_ = c
        return (r_ > 235 and g_ > 235 and b_ > 235) or (b_ >= r_ + 6 and b_ >= g_ - 2 and g_ < 120)
    sea = [False] * (nx * ny)
    stack = [(i, ny - 1) for i in range(nx) if z[(ny - 1) * nx + i] <= 0 and agua(cols[(ny - 1) * nx + i])]
    while stack:
        i, j = stack.pop()
        k = j * nx + i
        if sea[k]: continue
        sea[k] = True
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = i + di, j + dj
            if 0 <= a < nx and 0 <= b < ny and not sea[b * nx + a] \
               and z[b * nx + a] <= 0 and agua(cols[b * nx + a]):
                stack.append((a, b))
    d.pop("sea", None)                 # la página usa el contorno, no las celdas
    d["seapolys"] = contorno(sea, nx, ny, x0, y0, st)
    for k in ("pal", "c"): d.pop(k, None)
    d["note"] = d["note"].split(";")[0] + "; sea: máscara de mar por inundación desde la ortofoto PNOA (scripts/fetch_ortho.py)"
    json.dump(d, open(DEM, "w"), separators=(",", ":"))
    print(f"{DEM}: {sum(sea)} nodos de mar, "
          f"{os.path.getsize(DEM)/1024:.0f} KB", file=sys.stderr)
    Image.open(io.BytesIO(png)).save(os.path.join(os.environ.get("CLAUDE_JOB_DIR", "/tmp"), "tmp", "ortho.png"))


if __name__ == "__main__":
    main()
