#!/usr/bin/env python3
"""Eventos deportivos y pruebas populares de Donostia → tabla `event`.

Kulturklik (harvest_events.py) es agenda cultural: ni deporte, ni hora, ni
recinto con coordenadas. Lo que más mueve la red (Anoeta lleno, la Behobia,
las regatas) sale de aquí:

- openfootball (GitHub, sin clave): calendario completo de Primera División.
  Las fechas son provisionales hasta que LaLiga las confirma (todas salen
  "domingo 17:00" al principio); se marcan confirmed=false.
- TheSportsDB (clave pública "3"): próximo y último partido de la Real y del
  Gipuzkoa Basket, con fecha y hora confirmadas. El calendario de temporada
  completo es de pago, por eso la combinación con openfootball.
- Reglas de calendario para lo que es fijo por reglamento: Bandera de la
  Concha (primer y segundo domingo de septiembre) y Behobia-San Sebastián
  (segundo domingo de noviembre). Se generan para el año en curso y el
  siguiente sin mantenimiento.
- data/eventos-populares.csv: lo que varía cada año (Clásica, maratón). No hay
  fuente abierta estructurada: Kulturklik no tiene deporte, el CKAN de
  Donostia no tiene agenda, Wikidata se queda en 2015/2025 sin fechas
  exactas y las webs oficiales bloquean scrapers. Una línea al año, a mano.

Solo partidos EN CASA. Idempotente (upsert por id). Cron diario.
"""
import csv, json, os, re, sys, urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import psycopg2

DSN = os.environ["DBIZI_DSN"]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TZ = ZoneInfo("Europe/Madrid")
UA = {"User-Agent": "txirrin (github sanhuaaan/txirrin)"}
VENUES = {  # recinto -> (nombre, lat, lon)
    "anoeta":  ("Reale Arena (Anoeta)", 43.3014, -1.9735),
    "illumbe": ("Donostia Arena (Illumbe)", 43.2960, -1.9725),
}
TEAMS = {   # TheSportsDB idTeam -> (nombre corto, kind, recinto, patrones de nombre)
    "133724": ("Real Sociedad", "futbol", "anoeta", ("real sociedad",)),
    "135084": ("Gipuzkoa Basket", "baloncesto", "illumbe", ("gipuzkoa basket", "gipuzkoa")),
}
OPENFOOTBALL = "https://raw.githubusercontent.com/openfootball/espana/master/{season}/1-liga.txt"
TSDB = "https://www.thesportsdb.com/api/v1/json/3/{what}.php?id={id}"
MESES = {m: i for i, m in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read().decode("utf-8")


def temporada(hoy):
    y = hoy.year if hoy.month >= 7 else hoy.year - 1
    return f"{y}-{str(y + 1)[2:]}"


def parse_openfootball(txt):
    """Partidos en casa de la Real: (fecha local, hora|None, rival)."""
    out, year, day, last_mon = [], None, None, 0
    for line in txt.splitlines():
        m = re.match(r"^#\s*Date\s+\w+ (\w+) (\d+) (\d{4})", line)
        if m: year = int(m.group(3)); continue
        m = re.match(r"^\s*(Mon|Tue|Wed|Thu|Fri|Sat|Sun) (\w{3}) (\d+)(?: (\d{4}))?\s*$", line)
        if m:
            mon = MESES[m.group(2)]
            if m.group(4): year = int(m.group(4))          # año explícito: manda
            elif year is not None and mon < last_mon: year += 1   # el mes retrocede: año nuevo
            last_mon = mon
            if year is None: continue
            day = datetime(year, mon, int(m.group(3)))
            continue
        m = re.match(r"^\s*(?:(\d{1,2}:\d{2})\s+)?(.+?)\s+v\s+(.+?)\s*$", line)
        if m and day is not None and "Real Sociedad" in m.group(2):
            out.append((day, m.group(1), m.group(3).strip()))
    return out


def upsert(cur, row):
    cur.execute("""INSERT INTO event (id, source, kind, name, starts_at, ends_at, venue, lat, lon, confirmed, harvested_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
                   ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, starts_at=EXCLUDED.starts_at,
                     ends_at=EXCLUDED.ends_at, venue=EXCLUDED.venue, lat=EXCLUDED.lat, lon=EXCLUDED.lon,
                     confirmed=EXCLUDED.confirmed, harvested_at=now()""", row)


def main():
    hoy = datetime.now(TZ)
    conn = psycopg2.connect(DSN); cur = conn.cursor(); n = {"openfootball": 0, "thesportsdb": 0, "manual": 0}

    # 1) openfootball: toda la temporada, provisional
    try:
        txt = get(OPENFOOTBALL.format(season=temporada(hoy)))
        v = VENUES["anoeta"]
        for day, hora, rival in parse_openfootball(txt):
            h, mi = map(int, (hora or "17:00").split(":"))
            start = day.replace(hour=h, minute=mi, tzinfo=TZ)
            upsert(cur, (f"openfootball:{day:%Y%m%d}:{rival}", "openfootball", "futbol",
                         f"Real Sociedad - {rival}", start, start + timedelta(hours=2), v[0], v[1], v[2],
                         bool(hora) and False))   # la hora de openfootball también es provisional
            n["openfootball"] += 1
    except Exception as e:
        print(f"openfootball: {e}", file=sys.stderr)

    # 2) TheSportsDB: próximo y último, confirmados; pisan al provisional del mismo día
    for tid, (team, kind, recinto, pats) in TEAMS.items():
        for what, key in (("eventsnext", "events"), ("eventslast", "results")):
            try:
                data = json.loads(get(TSDB.format(what=what, id=tid))).get(key) or []
            except Exception as e:
                print(f"thesportsdb {team} {what}: {e}", file=sys.stderr); continue
            v = VENUES[recinto]
            for e in data:
                if e.get("idHomeTeam") != tid or not e.get("strTimestamp"): continue
                start = datetime.fromisoformat(e["strTimestamp"]).replace(tzinfo=timezone.utc)
                rival = e.get("strAwayTeam") or "?"
                local = start.astimezone(TZ)
                if kind == "futbol":   # quita el provisional de openfootball de ese día
                    cur.execute("DELETE FROM event WHERE source='openfootball' AND kind='futbol' AND (starts_at AT TIME ZONE 'Europe/Madrid')::date = %s", (local.date(),))
                upsert(cur, (f"thesportsdb:{e['idEvent']}", "thesportsdb", kind, f"{team} - {rival}",
                             start, start + timedelta(hours=2), v[0], v[1], v[2], True))
                n["thesportsdb"] += 1

    # 3a) pruebas populares con fecha reglamentaria: por regla, sin mantenimiento
    def domingo_n(y, mes, n):
        d = datetime(y, mes, 1, tzinfo=TZ)
        d += timedelta(days=(6 - d.weekday()) % 7)
        return d + timedelta(weeks=n - 1)
    for y in (hoy.year, hoy.year + 1):
        for n_, d in ((1, domingo_n(y, 9, 1)), (2, domingo_n(y, 9, 2))):
            start = d.replace(hour=12)
            upsert(cur, (f"manual:concha-{y}-{n_}", "regla", "regata", f"Bandera de la Concha ({n_}ª jornada)",
                         start, start + timedelta(hours=3), "Bahía de la Concha", 43.3185, -1.9905, True))
        start = domingo_n(y, 11, 2).replace(hour=10, minute=30)
        upsert(cur, (f"manual:behobia-{y}", "regla", "carrera", "Behobia - San Sebastián",
                     start, start + timedelta(hours=4), "Boulevard (meta)", 43.3218, -1.9835, True))
        n["manual"] += 3

    # 3b) lo que varía cada año, a mano
    with open(os.path.join(ROOT, "data", "eventos-populares.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            h, mi = map(int, r["time"].split(":"))
            start = datetime.fromisoformat(r["date"]).replace(hour=h, minute=mi, tzinfo=TZ)
            upsert(cur, (f"manual:{r['id']}", "manual", r["kind"], r["name"], start, start + timedelta(hours=4),
                         r["venue"], float(r["lat"]), float(r["lon"]), r["confirmed"].lower() == "true"))
            n["manual"] += 1
    conn.commit()
    print(f"event: {n}", file=sys.stderr)


if __name__ == "__main__":
    main()
