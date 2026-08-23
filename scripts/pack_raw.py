#!/usr/bin/env python3
"""Empaqueta un día de crudo (~/raw/YYYYMMDD/*.json.gz) en ~/raw/YYYYMMDD.tar.xz.

Por qué: subir 720 ficheros/día a GCS son 21.000 operaciones/mes, cuatro
veces la capa gratuita (5.000). Un tar por día es una. Se empaqueta el JSON
DESCOMPRIMIDO y se comprime el tar entero con xz: 720 snapshots casi iguales
comprimen juntos mucho mejor que uno a uno. Medido con un día real:
sueltos 1,09 MB, tar.gz 1,06 (la ventana de 32 KB de gzip no ve de un
snapshot al siguiente), tar.xz nivel 1: 0,36 MB en 0,2 s y 11 MB de RAM.

Los .bad (crudo que no validó) van dentro también: son la prueba de qué
devolvió el feed. Los .tmp (escritura interrumpida) no. Escritura atómica.

Uso: pack_raw.py YYYYMMDD [...]   (sin args: hoy y ayer, UTC)
"""
import gzip, io, os, sys, tarfile
from datetime import datetime, timedelta, timezone

RAW = os.environ.get("DBIZI_RAW_DIR", os.path.expanduser("~/raw"))


def pack(day):
    src = os.path.join(RAW, day)
    if not os.path.isdir(src):
        return None
    out = os.path.join(RAW, day + ".tar.xz"); tmp = out + ".tmp"
    n = 0
    with tarfile.open(tmp, "w:xz", preset=1) as tar:   # preset 1: 11 MB de RAM, la e2-micro lo agradece
        for fname in sorted(os.listdir(src)):
            if not fname.endswith(".json.gz"):
                continue
            try:
                with gzip.open(os.path.join(src, fname), "rb") as f:
                    data = f.read()
            except (OSError, EOFError):
                continue                      # truncado: no hay nada que guardar
            info = tarfile.TarInfo(f"{day}/{fname[:-3]}")   # .json.gz -> .json
            info.size = len(data)
            info.mtime = int(datetime.strptime(day + fname[:6], "%Y%m%d%H%M%S")
                             .replace(tzinfo=timezone.utc).timestamp())
            tar.addfile(info, io.BytesIO(data)); n += 1
    os.replace(tmp, out)
    return out, n


def main():
    days = sys.argv[1:]
    if not days:
        hoy = datetime.now(timezone.utc)
        days = [(hoy - timedelta(days=1)).strftime("%Y%m%d"), hoy.strftime("%Y%m%d")]
    for d in days:
        r = pack(d)
        if r: print(f"{r[0]}: {r[1]} snapshots, {os.path.getsize(r[0])/1024:.0f} KB")


if __name__ == "__main__":
    main()
