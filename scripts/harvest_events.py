#!/usr/bin/env python3
"""Cosecha diaria de Kulturklik: la API purga el pasado, así que archivamos ya
aunque la fase de eventos no haya llegado. Solo crudo gzip; sin normalizar.

Guarda mes actual + siguiente (todas las páginas) en ~/events/events_YYYYMMDD.json.gz.
Cron diario en la VM; el backup diario sube ~/events a GCS.
"""
import gzip
import json
import os
import urllib.request
from datetime import datetime, timezone

OUT = os.path.expanduser("~/events")
URL = ("https://api.euskadi.eus/culture/events/v1.0/events/"
       "byMonth/{y}/{m}/byMunicipality/20/82?_page={p}")  # 20/82 = Donostia en código NORA


def fetch_month(y, m):
    items, page = [], 1
    while True:
        req = urllib.request.Request(
            URL.format(y=y, m=m, p=page),
            headers={"User-Agent": "dbizi-events", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
        items += data.get("items", [])
        if page >= int(data.get("totalPages") or 1):
            return items
        page += 1


def main():
    now = datetime.now(timezone.utc)
    y2, m2 = (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
    payload = {
        "harvested_at": now.isoformat(),
        "months": {
            f"{now.year}-{now.month:02d}": fetch_month(now.year, now.month),
            f"{y2}-{m2:02d}": fetch_month(y2, m2),
        },
    }
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"events_{now.strftime('%Y%m%d')}.json.gz")
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    print(f"{sum(len(v) for v in payload['months'].values())} eventos -> {path}")


if __name__ == "__main__":
    main()
