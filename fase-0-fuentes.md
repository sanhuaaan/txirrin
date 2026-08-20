# Fase 0 — Validación de fuentes (2026-08-20)

Resultado de la validación real de las cuatro fuentes: llamadas efectivas a las APIs, evidencia comprobada. Veredicto global al final.

---

## 🚲 Dbizi — ✅ EXCELENTE

**Feed GBFS oficial, público, sin autenticación**, operado por PBSC/Lyft y listado en el catálogo de MobilityData.

- Feed: `https://sansebastian.publicbikesystem.net/customer/gbfs/v3.0/gbfs.json` (también v2.3 y v1.1).
- `station_information`: **70 estaciones** con lat/lon, dirección, capacidad, nombres es/eu.
- `station_status`: bicis y anclajes disponibles por estación, `last_reported` en segundos, **desglose mecánica (FIT/ICONIC/METRO) vs. eléctrica (EFIT/BOOST/COSMO/ASTRO)**.
- TTL 21–30 s → tiempo casi real.
- **Sin histórico**: hay que auto-archivar (collector). citybik.es agrega la red como posible respaldo.

## 🅿️ Parkings — ✅ MEJOR DE LO ESPERADO: hay fuente dinámica

- **Dinámico** (¡existe!): `https://www.donostia.eus/info/ciudadano/camaras_trafico.nsf/getParkings.xsp` — GeoJSON, sin key, **16 parkings subterráneos con plazas libres en vivo** (`libres`, `plazasRotatorias`, `plazasResidentesLibres`, tarifas, coordenadas UTM ETRS89 huso 30). Es la fuente de los paneles de guiado.
  - Matices: 6/16 devuelven `libres: "0"` (probablemente no reportan); cadencia de refresco sin confirmar; silo Lotus Domino fuera del catálogo CKAN (fragilidad: el dataset CKAN equivalente antiguo da 404).
- **Estático**: portal CKAN 2.11.2 con API estándar (`/datosabiertos/api/3/action/package_search`). 11 datasets de aparcamiento (subterráneos, disuasorios, OTA, PMR, motos…) en SHP/GeoJSON/CSV/WMS.
- **Geografía**: barrios (`auzoak.json` GeoJSON directo), ejes viales, carril bici, callejero — todo descargable.
- **Bonus**: `getCamaras.xsp` — 28 cámaras de tráfico con snapshots JPG.

## 🌧️ Euskalmet — ✅ RESUELTO, con matiz

- **Histórico**: zips anuales gratuitos sin key, `https://opendata.euskadi.eus/contenidos/ds_meteorologicos/met_stations_ds_{YYYY}/opendata/{YYYY}.zip`, desde 2003, **granularidad 10 min**, XML por estación/mes (ISO-8859-1), licencia CC BY.
- **Tiempo real**: API `api.euskadi.eus/euskalmet` con key gratuita (portal `opendata-apikey`) + JWT RS256 (`aud: "met01.apikey"`). Sandbox sin auth (`api.sandbox.euskadi.eus`, datos 2020-2022) para desarrollar.
- **Matiz**: en Donostia solo 4 estaciones Euskalmet, 2 de ellas hidrológicas. La única completa con **precipitación es C017 Miramón** (43.2868, -1.97121; alta ~2010 → el histórico útil empieza ahí). **C007 Santa Clara** apoya con viento/temperatura pero no mide lluvia. Igeldo es de AEMET, no Euskalmet. Cercanas: Lasarte, Hernani, Oiartzun, Pasaia.
- Catálogo de estaciones con coordenadas: `.../estaciones_meteorologicas/opendata/estaciones.json` (también GeoJSON).

## 🚗 Tráfico — ❌ EL AGUJERO

La API `api.euskadi.eus/traffic` es abierta (sin key, CC BY), bien estructurada, con aforos de 15–30 min que incluyen intensidad, velocidad media e histogramas de velocidad/longitud. **Pero para Donostia está muerta:**

- Los **187 medidores urbanos del Ayuntamiento (fuente 7) nunca han publicado una medición** — inventariados con coordenadas, cero flows en todas las fechas probadas (2018–2026).
- Los 9 medidores de la **GI-20 (fuente 1)** publicaron de **2016 a noviembre de 2024** y desde entonces nada. Hoy solo Bilbao y Vitoria alimentan la API.
- El portal CKAN municipal no tiene ningún dataset de aforos/espiras (el de "ubicación de espiras" 2020 tiene el enlace roto).
- **Vivo hoy**: incidencias en tiempo real con coordenadas (~30-80k/año desde 2021) y cámaras.
- **Alternativa real**: **Gipuzkoa Irekia (DFG)** — "Datos de tráfico semanales": CSV/JSON, 30 min por detector/carril, 75 ETDs, 2020–2025, cubre accesos a Donostia (GI-20, GI-20-10, GI-40, GI-41, A-15, N-I) pero **no viario urbano**. Descarga vía proxy del portal (los enlaces directos a `opepro08.sare.gipuzkoa.net` no resuelven en DNS público). Dataset de estaciones con GeoJSON actualizado 2026-08.

---

## Veredicto y decisiones

1. **El MVP pivota: Dbizi + parkings + meteo**, no tráfico + meteo. Las dos fuentes de comportamiento (bicis cada 30 s, parkings en vivo) son abiertas, limpias y con coordenadas; la de tráfico urbano no existe.
2. **El collector debe arrancar cuanto antes**: ni Dbizi ni parkings tienen histórico — cada día sin recolectar es un día perdido de serie temporal.
3. **Meteo**: C017 Miramón como estación de referencia (lluvia); histórico 10-min descargable ya. Para una ciudad de este tamaño, una estación de precipitación basta para el MVP.
4. **Tráfico queda como dimensión secundaria**: histórico GI-20 2016–2024 (descargable por API) + aforos DFG 2020–2025 sirven para análisis retrospectivo de accesos; incidencias en vivo como factor explicativo de anomalías. Reevaluar si el Ayuntamiento/GV reactivan la publicación.
5. La pregunta inicial se reformula:

> ¿Cómo cambian el uso de Dbizi y la ocupación de parkings en Donostia en función de la meteorología?

---

# Anexo — Fuente de eventos (validada 2026-08-20)

## 🎫 Eventos — ✅ RESUELTO con tres piezas

### 1. API Kulturklik (Open Data Euskadi) — fuente principal

```text
https://api.euskadi.eus/culture/events/v1.0/events/byMonth/{año}/{mes}/byMunicipality/20/82
```

Sin key, JSON limpio, paginado (`_page=N`, 20/página). Ago-2026 → 287 eventos: **Semana Grande** (conciertos con plaza y hora), Illumbe/Donostia Arena, Kursaal, Victoria Eugenia, salas pequeñas (Dabadaba…).

- ⚠️ Donostia = provincia **20**, municipio **82** (código NORA — el 69 es Astigarraga).
- Campos: nombre es/eu, `startDate`/`endDate` (día), `openingHoursEs` (hora inicio en texto libre), `establishmentEs` (venue), tipo, precio.
- ⚠️ `municipalityLatitude/Longitude` es el **centroide del municipio** — geocodificar a mano los ~30-50 venues recurrentes (tabla `venue → coords`, una vez).
- ⚠️ **La API purga el pasado** (verificado: 2024/2022 vacíos) → cron diario y el histórico lo construimos nosotros.
- Descartar del análisis exposiciones de larga duración (`endDate - startDate` grande).

### 2. TheSportsDB — Anoeta/Reale Arena (~40k personas)

```text
https://www.thesportsdb.com/api/v1/json/3/eventsnext.php?id=133724
```

Key pública `3` gratis; Real Sociedad = `idTeam 133724`. Da `dateEventLocal`, `strTimeLocal` (hora local), `strVenue` → filtrar `"Reale Arena"` para partidos en casa. Histórico por temporada vía `eventsseason.php`. Alternativa si el rate limit molesta: football-data.org (key gratuita, no verificada).

### 3. Scraper Kursaal — solo congresos

`https://www.kursaal.eus/es/tipo/reuniones/` — WordPress sin API (post type no expuesto en wp-json, sin JSON-LD Event), pero HTML estable con título, fecha y hora. Lo cultural del Kursaal ya llega vía Kulturklik; los **congresos** (Gastronomika, ICDMS…) no, y mueven miles de personas. Venue fijo: 43.3277, -1.9755.

### Descartados (con evidencia)

- **CKAN municipal**: 140 datasets, cero de agenda/eventos.
- **Silo Domino** (`getEventos.xsp` y similares): 404, donostia.eus migró a Liferay; la agenda web nueva es HTML server-rendered sin API (y su contenido ya fluye a Kulturklik).
- **Donostia Kultura**: Cloudflare bloquea el acceso directo, pero es fuente ingerida por Kulturklik (verificado en `sourceNameEs`).
- **Eventbrite**: retiró la API pública de búsqueda. **Songkick/Bandsintown**: keys cerradas/con aprobación, redundantes. **Ticketmaster**: key gratuita disponible, cobertura Donostia sin verificar — innecesario de momento. **PredictHQ**: de pago, es exactamente este producto si algún día se quiere pagar.
