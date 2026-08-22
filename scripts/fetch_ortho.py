#!/usr/bin/env python3
"""Color de cada celda del relieve a partir de la ortofoto real (PNOA, IGN).

Lee la rejilla de viz/donostia-dem.json, pide al WMS del IGN la ortofoto del
mismo recuadro a PX_POR_CELDA píxeles por celda, promedia cada bloque y
cuantiza el resultado a una paleta corta (median cut). Guarda en el propio
JSON `pal` (la paleta) y `c` (índice por nodo). Así cada celda es un píxel:
pixel art de la ciudad a 50 m, no una foto pegada.

El mar es el índice 0: celdas a cota 0 cuya ortofoto es azul o blanca (el
PNOA no cubre mar abierto y devuelve blanco). Se ejecuta una vez; necesita
Pillow solo aquí, la página no.
"""
import io, json, math, os, sys, urllib.request
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEO = os.path.join(ROOT, "viz", "donostia-barrios.json")
DEM = os.path.join(ROOT, "viz", "donostia-dem.json")
M_DEG = 111320.0
PX_POR_CELDA = 4
COLORES = 16
WMS = ("https://www.ign.es/wms-inspire/pnoa-ma?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap"
       "&LAYERS=OI.OrthoimageCoverage&STYLES=&CRS=EPSG:4326&BBOX={s},{w},{n},{e}"
       "&WIDTH={W}&HEIGHT={H}&FORMAT=image/png")


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
    cols = [None if sea[k] else cols[k] for k in range(nx * ny)]
    # Clasificación, no cuantización: una paleta extraída de la ortofoto da una
    # foto pegada (gris-verde con ruido). Aquí cada celda cae en una clase por
    # su color real y la clase tiene un color ELEGIDO. Estructura real, pixel art.
    CLASES = [  # (nombre, color estilizado)
        ("mar",     [16, 36, 55]),
        ("bosque",  [34, 68, 50]),
        ("prado",   [88, 132, 70]),
        ("casco",   [138, 132, 128]),
        ("claro",   [184, 178, 164]),
        ("arena",   [214, 190, 122]),
    ]
    # Umbrales calibrados sobre el PNOA de Donostia (velo azulado costero: lo
    # que separa es la luminancia y el verde relativo): Gros/Amara lum~160,
    # Zurriola 210, bosque de Igeldo 72, Anoeta 104.
    def clase(c):
        r_, g_, b_ = c
        l = 0.299 * r_ + 0.587 * g_ + 0.114 * b_
        verde = g_ - r_
        if l > 190 and r_ - b_ >= 4: return 5                         # arena
        if l > 185:      return 4                                     # vial, solar, tejado claro
        if verde >= 12:  return 2 if l >= 100 else 1                  # prado / bosque
        if l >= 120:     return 3                                     # casco
        return 1                                                      # oscuro: bosque
    idx = [0 if c is None else clase(c) for c in cols]
    d["pal"] = [c[1] for c in CLASES]
    from collections import Counter
    print({CLASES[k][0]: n for k, n in sorted(Counter(idx).items())}, file=sys.stderr)
    d["c"] = idx
    d["note"] += "; pal/c: color por nodo desde la ortofoto PNOA (IGN), 0 = mar (scripts/fetch_ortho.py)"
    json.dump(d, open(DEM, "w"), separators=(",", ":"))
    print(f"{DEM}: {len(CLASES)} clases, {sum(1 for i in idx if i == 0)} nodos de mar, "
          f"{os.path.getsize(DEM)/1024:.0f} KB", file=sys.stderr)
    Image.open(io.BytesIO(png)).save(os.path.join(os.environ.get("CLAUDE_JOB_DIR", "/tmp"), "tmp", "ortho.png"))


if __name__ == "__main__":
    main()
