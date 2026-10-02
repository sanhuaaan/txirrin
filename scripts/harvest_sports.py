#!/usr/bin/env python3
"""Eventos deportivos y pruebas populares de Donostia → tabla `event`.

Kulturklik (harvest_events.py) es agenda cultural: ni deporte, ni hora, ni
recinto con coordenadas. Lo que más mueve la red (Anoeta lleno, la Behobia,
las regatas) sale de aquí:

- realsociedad.eus (la web del club): el próximo partido del primer equipo con
  hora Y RECINTO. Es la única fuente que trae los amistosos (el derbi del
  parón, por ejemplo) y la Copa, y la única que dice dónde se juega, así que
  manda sobre las demás. Se lee el microdato schema.org del widget "próximo
  partido" y la tarjeta "dd/mm/aaaa · HH:MM · Recinto"; solo se guarda si el
  recinto es Anoeta.
- openfootball (GitHub, sin clave): calendario completo de Primera División.
  Las fechas son provisionales hasta que LaLiga las confirma (todas salen
  "domingo 17:00" al principio); se marcan confirmed=false.
- TheSportsDB (clave pública "3"): próximo y último partido de la Real y del
  Gipuzkoa Basket, con fecha y hora confirmadas; cubre Europa League y Copa,
  que openfootball no tiene. La clave pública está capada a UN partido por
  consulta (el calendario de temporada entero es de pago), de ahí la mezcla.
- Reglas de calendario para lo que es fijo por reglamento: Bandera de la
  Concha (primer y segundo domingo de septiembre) y Behobia-San Sebastián
  (segundo domingo de noviembre). Se generan para el año en curso y el
  siguiente sin mantenimiento.
- data/eventos-populares.csv: lo que varía cada año (Clásica, maratón). No hay
  fuente abierta estructurada: Kulturklik no tiene deporte, el CKAN de
  Donostia no tiene agenda, Wikidata se queda en 2015/2025 sin fechas
  exactas y las webs oficiales bloquean scrapers. Una línea al año, a mano.

Solo partidos EN CASA. Idempotente: el id es canónico por deporte, recinto y
día (`futbol:anoeta:20261002`), no por fuente, así que las tres fuentes
escriben sobre la misma fila en vez de duplicarla; gana la de más autoridad
(club > TheSportsDB > openfootball) y una fuente peor nunca pisa a una mejor.

El histórico manda: un partido capturado no se borra nunca, porque es lo que
explica la marea de bicis de aquel día meses después. La única excepción son
los fantasmas de openfootball —días que su propio calendario ya no da como
jornada, porque LaLiga movió el partido— y solo mientras ninguna fuente mejor
haya confirmado esa fila.
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
RS_PARTIDOS = "https://www.realsociedad.eus/es/equipo/partidos/real-sociedad"
# quién manda cuando dos fuentes hablan del mismo partido
PRIO = {"realsociedad": 3, "thesportsdb": 2}
CASE = "CASE {} WHEN 'realsociedad' THEN 3 WHEN 'thesportsdb' THEN 2 ELSE 1 END"
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
            # jugado: la línea lleva el marcador pegado al rival ("... v Elche CF  2-3 (0-2)")
            rival = re.sub(r"\s{2,}\d+-\d+(?:\s*\(\d+-\d+\))?$", "", m.group(3)).strip()
            out.append((day, m.group(1), rival))
    return out


def parse_realsociedad(h):
    """Próximo partido del primer equipo: (inicio local, rival, recinto)."""
    t = re.search(r'class="competitor first".*?content="([^"]+)".*?class="competitor last".*?content="([^"]+)"', h, re.S)
    card = None
    for m in re.finditer(r'matchphase-location-date"[^>]*>(.*?)</div>', h, re.S):
        partes = [p.strip() for p in re.sub(r"<[^>]+>", "·", m.group(1)).split("·") if p.strip()]
        if partes and re.fullmatch(r"\d{2}/\d{2}/\d{4}", partes[0]) and len(partes) >= 3:
            card = partes; break
    if not (t and card): return None
    # la hora buena es la de la tarjeta: el microdato startDate lleva una "Z"
    # que no es cierta (el club publica hora local marcada como UTC)
    dia = datetime.strptime(card[0], "%d/%m/%Y")
    hh, mm = map(int, card[1].split(":"))
    local, visitante, recinto = t.group(1).strip(), t.group(2).strip(), card[-1]
    if "real sociedad" not in local.lower(): return None      # fuera de casa
    return dia.replace(hour=hh, minute=mm, tzinfo=TZ), visitante, recinto


def upsert(cur, row):
    """Escribe la fila del día; una fuente de menos autoridad no pisa a otra mejor."""
    cur.execute(f"""INSERT INTO event (id, source, kind, name, starts_at, ends_at, venue, lat, lon, confirmed, harvested_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
                   ON CONFLICT (id) DO UPDATE SET source=EXCLUDED.source, name=EXCLUDED.name,
                     starts_at=EXCLUDED.starts_at, ends_at=EXCLUDED.ends_at, venue=EXCLUDED.venue,
                     lat=EXCLUDED.lat, lon=EXCLUDED.lon, confirmed=EXCLUDED.confirmed, harvested_at=now()
                   WHERE {CASE.format('EXCLUDED.source')} >= {CASE.format('event.source')}""", row)


def eid(kind, recinto, dia):
    """Id canónico: un partido por deporte, recinto y día, venga de donde venga."""
    return f"{kind}:{recinto}:{dia:%Y%m%d}"


def main():
    hoy = datetime.now(TZ)
    conn = psycopg2.connect(DSN); cur = conn.cursor(); n = {"openfootball": 0, "thesportsdb": 0, "manual": 0}

    # 1) openfootball: toda la temporada, provisional (la peor fuente, va primero)
    try:
        txt = get(OPENFOOTBALL.format(season=temporada(hoy)))
        v = VENUES["anoeta"]
        vivos, dias = [], []
        for day, hora, rival in parse_openfootball(txt):
            dias.append(day.replace(tzinfo=TZ))
            h, mi = map(int, (hora or "17:00").split(":"))
            start = day.replace(hour=h, minute=mi, tzinfo=TZ)
            i = eid("futbol", "anoeta", day); vivos.append(i)
            upsert(cur, (i, "openfootball", "futbol",
                         f"Real Sociedad - {rival}", start, start + timedelta(hours=2), v[0], v[1], v[2],
                         False))   # la hora de openfootball también es provisional
            n["openfootball"] += 1
        # Fantasmas: LaLiga mueve partidos de día y el anterior se queda ahí
        # (el Celta del 16 de septiembre se jugó el 3). El fichero trae la
        # temporada entera, jugados incluidos, así que es la autoridad sobre
        # qué días hubo partido: lo que no está en él, no se jugó. Solo se
        # borran filas que siguen siendo suyas —si TheSportsDB o el club la
        # confirmaron, la fila ya no es de openfootball y no se toca— y solo
        # dentro de la temporada que acabamos de leer.
        dias.sort()
        if vivos:
            cur.execute("""DELETE FROM event WHERE source='openfootball'
                             AND starts_at BETWEEN %s AND %s AND NOT (id = ANY(%s))""",
                        (dias[0], dias[-1] + timedelta(days=1), vivos))
            n["fantasmas"] = cur.rowcount
    except Exception as e:
        print(f"openfootball: {e}", file=sys.stderr)

    # 2) TheSportsDB: próximo y último, confirmados
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
                upsert(cur, (eid(kind, recinto, local), "thesportsdb", kind, f"{team} - {rival}",
                             start, start + timedelta(hours=2), v[0], v[1], v[2], True))
                n["thesportsdb"] += 1

    # 3) la web del club: el próximo partido con hora y recinto. Única fuente de
    # los amistosos (el derbi del parón no está en ninguna otra) y la que manda.
    try:
        r = parse_realsociedad(get(RS_PARTIDOS))
        if r is None:
            print("realsociedad: sin próximo partido en casa", file=sys.stderr)
        elif "anoeta" not in r[2].lower() and "reale" not in r[2].lower():
            print(f"realsociedad: próximo partido fuera ({r[2]})", file=sys.stderr)
        else:
            start, rival, _ = r; v = VENUES["anoeta"]
            upsert(cur, (eid("futbol", "anoeta", start), "realsociedad", "futbol",
                         f"Real Sociedad - {rival}", start, start + timedelta(hours=2), v[0], v[1], v[2], True))
            n["realsociedad"] = n.get("realsociedad", 0) + 1
    except Exception as e:
        print(f"realsociedad: {e}", file=sys.stderr)

    # 4a) pruebas populares con fecha reglamentaria: por regla, sin mantenimiento
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

    # 4b) lo que varía cada año, a mano
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
