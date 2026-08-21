# Fuentes futuras — catálogo evaluado

Investigación verificada con llamadas reales (2026-08-21, tres barridos: transporte público, sensórica/ambiente, contexto socioeconómico). Regla de admisión del proyecto:

> **Una fuente nueva debe permitir responder una pregunta nueva sobre el comportamiento de Dbizi.**

## Tier 1 — listas para ingerir, valor alto

| Fuente | Qué da | Endpoint verificado | Pregunta nueva |
|--------|--------|---------------------|----------------|
| **Calidad del aire** (Euskadi) | NO2/PM/O3 **horario**, 7 estaciones en Donostia, ~10 años de histórico vía API, sin key. Bonus: la estación de Puio da **meteo horaria local** (lluvia, viento, Tª) — segunda fuente meteo gratis | `api.euskadi.eus/air-quality/measurements/hourly/stations/{id}/from/{f}/to/{t}` | ¿Los episodios de NO2/PM deprimen el uso? ¿El ozono de verano modula los picos de tarde? |
| **Ocupación hotelera DIARIA** (Eustat) | Pernoctaciones/entradas/ocupación de Donostia **por día**, desde 2022, API JSON-stat2, actualización mensual | `POST eustat.eus/bankupx/api/v1/es/DB/PX_132680_cetr_etrm_20h.px` | ¿El agosto anómalo es turismo o vacaciones locales? ¿Las estaciones de playa siguen a las pernoctaciones día a día? |
| **Euskotren GTFS-RT** (Moveuskadi) | Retrasos del Topo **en vivo** (verificado fresco), sin key. Sin histórico → auto-archivar | `opendata.euskadi.eus/transport/moveuskadi/euskotren/gtfsrt_euskotren_trip_updates.pb` | ¿Un día de retrasos del Topo sube Dbizi en Gros/Intxaurrondo/Herrera? (sustitución modal) |
| **Renfe Cercanías RT** | `alerts.json` (¡JSON, no protobuf!) con obras/incidencias vivas, cadencia ~30 s; + dataset de **viajeros por franja horaria y estación** | `gtfsrt.renfe.com/alerts.json` · data.renfe.com | ¿Las incidencias de C1 empujan gente a Dbizi? ¿Intermodalidad tren+bici por franja? |
| **Renta/demografía por barrio** (CKAN Donostia) | Renta (desde 2016), pirámide de edad, paro por barrio y unidad menor, CSV + GeoJSON casando por `CodBarrio` con los barrios que ya usamos | `datosabiertos/api/3/action/package_show?id=eustat_renta` | ¿Estaciones de barrios de renta baja (Altza 14,3k€) = commute obligado vs renta alta (Aiete 24,9k€) = ocio? Carga anual, estática |

## Tier 2 — baratas, valor medio

- **Tablas a mano (1h/año)**: calendario escolar Gipuzkoa (solo PDF oficial — driver enorme lectivo/no-lectivo), calendario universitario EHU (campus Ibaeta como polo), eventos deportivos con cortes (Behobia, maratón, Clásica, Bandera de La Concha — ¿Dbizi se hunde o se dispara esos días?).
- **Dbus GTFS estático** (diario, Moveuskadi, verificado): frecuencias y shapes → ¿estaciones Dbizi sobre corredores con mucho bus rotan menos? ¿Dbizi absorbe el recorte estacional de servicio de agosto?
- **Mareas y estado del mar** (Portus/Puertos del Estado, API interna sin auth — no documentada, riesgo de cambio): mareógrafo Pasaia y boya Bilbao en vivo + histórico horario → ¿marea baja = más Dbizi a Zurriola? ¿Mar grande = peregrinación al Paseo Nuevo?
- **Nivel del río Urumea** (CKAN municipal, XML cada 10 min, Txomin Enea/Martutene) → proxy de crecidas que cortan justamente el bidegorri del Urumea.
- **Playas** (web municipal server-rendered, scrapeable; banderas y mareas): ¿bandera roja en Zurriola redirige flujo a Concha/Ondarreta? Requiere auto-archivo.

## Tier 3 — bloqueadas o descartadas

- **Contadores de bicis/peatones en bidegorris** — la fuente que MÁS querríamos (bici privada vs Dbizi): la DFG los recoge desde 2012 pero **solo publica PDFs anuales**; el tótem de La Concha (Dinycon) no tiene plataforma pública. → **Candidata a petición de apertura de datos** a DFG/Ayuntamiento.
- **Validaciones MUGI** (ridership bus): no existe en abierto. → Petición a ATTG/DFG.
- **Dbus GTFS-RT**: publicado pero **congelado desde 2026-08-04** (el fichero se republica cada minuto con timestamp interno viejo — vigilar `header.timestamp`, no Last-Modified). Re-evaluar si revive.
- **Tráfico urbano**: muerto (ver `fase-0-fuentes.md`). **Ruido**: no hay red pública (peticiones vecinales rechazadas). **Cruceros**: volumen despreciable y dato mensual agregado — descartado.

## Recomendación de orden (cuando toque)

1. **Calidad del aire** — API impecable, histórico profundo, y regala una segunda estación meteo horaria en la ciudad (Puio).
2. **Eustat hotelero diario** — pequeña, mensual, y desbloquea la pregunta turismo-vs-local que el calendario solo no responde.
3. **Tablas a mano** (escolar + eventos deportivos) — una tarde, contexto permanente.
4. **Euskotren + Renfe RT** — cuando haya apetito de auto-archivar otro feed (mismo patrón que collect.py).
5. **Renta por barrio** — cuando el análisis por estación madure (fase 5-6).

Nada de esto se ingiere aún: el MVP sigue siendo bicis + meteo. Este catálogo es la despensa.
