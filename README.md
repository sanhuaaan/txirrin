# Donostia Mobility Intelligence

Proyecto personal de ingeniería de datos: observar, analizar y explicar el comportamiento de la movilidad urbana en Donostia-San Sebastián usando datos públicos.

> **La movilidad es el dominio; la ingeniería de datos es el verdadero proyecto.**

Pregunta inicial:

> ¿Cómo cambia el comportamiento normal de la movilidad de Donostia en función de las condiciones meteorológicas?

Evolución prevista:

> ¿Podemos detectar anomalías en la movilidad y encontrar factores que las expliquen?

No es una plataforma institucional ni un producto comercial. Donostia es el laboratorio.

---

## Fuentes de datos

Validadas el 2026-08-20 con llamadas reales — detalle y evidencia en [`fase-0-fuentes.md`](fase-0-fuentes.md).

| Fuente | Veredicto | Datos |
|--------|-----------|-------|
| 🚲 Dbizi | ✅ GBFS oficial sin auth (PBSC), TTL ~30 s | 70 estaciones, bicis/anclajes, eléctrica vs. mecánica. Sin histórico → collector |
| 🅿️ Donostia parkings | ✅ Dinámico: `getParkings.xsp` (sin key) | 16 subterráneos con plazas libres en vivo + CKAN estático (OTA, disuasorios, barrios, viales) |
| 🌧️ Euskalmet | ✅ Histórico 10-min desde 2003 (zips) + API con key gratuita | En Donostia, precipitación solo en **C017 Miramón** (desde ~2010) |
| 🚗 Tráfico Euskadi | ❌ Muerta para Donostia | 187 sensores urbanos sin datos jamás; GI-20 cortó en nov-2024. Vivo: incidencias y cámaras. Alternativa: aforos DFG 2020–2025 (accesos, no urbano) |
| 📅 Calendario | Tabla a mano (~14 filas/año) | Festivos de Gipuzkoa |

Extensiones posibles (no ahora): eventos (Anoeta, Kursaal), incidencias, transporte público, calidad del aire.

---

## Decisiones de diseño

Recortes deliberados de sobre-ingeniería. Cada uno tiene su condición de reapertura.

1. **Una sola aplicación collector con un job programado por fuente** — no un servicio por fuente. Son cuatro crons contra cuatro APIs escribiendo en la misma base de datos. *Se separa si algún día un collector necesita ciclo de vida o despliegue propio.*
2. **PostgreSQL + PostGIS, y nada más.** Sin TimescaleDB, sin ClickHouse. Particionado e índices de Postgres aguantan de sobra el volumen de una ciudad de 190k habitantes. *Se reevalúa si una query de agregación tarda segundos con índices correctos.*
3. **Exploración en notebook (pandas + folium/plotly) o Grafana sobre Postgres.** Sin frontend Vue ni API propia hasta que haya algo que enseñar a otros. *Se construye dashboard cuando exista audiencia.*
4. **Guardar siempre el crudo de las APIs** (JSONB o ficheros) además de lo normalizado. Las APIs públicas cambian de formato; el crudo permite re-procesar.
5. **Calendario = una tabla de festivos**, no un módulo.
6. **ML aplazado** hasta tener histórico suficiente y una pregunta que lo justifique.

---

## Fase 0 — validar las fuentes ✅ HECHA (2026-08-20)

Resultado en [`fase-0-fuentes.md`](fase-0-fuentes.md). Conclusión: **el tráfico urbano no existe como dato abierto** (sensores municipales inventariados pero mudos; GI-20 cortada desde nov-2024), y en cambio **Dbizi y parkings son excelentes y en tiempo real**. El MVP pivota.

---

## MVP v1 — Dbizi + parkings + meteorología

Ninguna de las dos fuentes de comportamiento tiene histórico: **el collector debe arrancar cuanto antes** — cada día sin recolectar es serie temporal perdida.

1. Collector archivando GBFS de Dbizi (~1 min) y `getParkings.xsp` (~5 min), crudo + normalizado.
2. Descargar histórico Euskalmet (zips 10-min) y cargar C017 Miramón.
3. Asociar estaciones Dbizi/parkings a la estación meteo (PostGIS; con una sola estación de lluvia, trivial).
4. Agregaciones horarias.
5. En cuanto haya unas semanas de datos, analizar en notebook:

> ¿Cómo cambian el uso de Dbizi y la ocupación de parkings cuando llueve?

Comparando siempre días comparables (lunes 08:30 con lluvia vs. lunes 08:30 seco, no vs. domingo).

El tráfico queda como dimensión secundaria: histórico GI-20 2016–2024 + aforos DFG 2020–2025 para retrospectiva de accesos, e incidencias en vivo como factor explicativo de anomalías.

---

## Modelo de datos

Fuentes separadas, patrón común `station` + `measurement`:

```text
traffic_station(id, name, geom, road, direction, source)
traffic_measurement(station_id, timestamp, vehicle_count, speed, occupancy, raw jsonb)

weather_station(id, name, geom, altitude, source)
weather_measurement(station_id, timestamp, temperature, precipitation, humidity, wind_speed, pressure, raw jsonb)

dbizi_station(id, name, geom, capacity, source)
dbizi_measurement(station_id, timestamp, bikes_available, docks_available, raw jsonb)

parking(id, name, geom, type, capacity, source)
parking_measurement(parking_id, timestamp, occupied, available, raw jsonb)   -- solo si aparece fuente dinámica

holiday(date, name)
```

`geom` = geometría PostGIS; permite "estación meteorológica más cercana", "parkings a menos de X metros", etc.

---

## Etapas

```text
0. Validar fuentes        → "Sé qué datos existen"
1. Ingestión              → "Consigo los datos"
2. Histórico fiable       → "Tengo series temporales limpias"
3. Exploración            → "Puedo observar qué pasa"
4. Análisis               → "Puedo cuantificar relaciones (lluvia → tráfico)"
5. Anomalías              → "Puedo detectar comportamientos anómalos"
6. Explicación            → "Puedo buscar qué factores los explican"
7. Predicción             → "Puedo anticipar qué puede ocurrir"
```

No es necesario llegar a la última etapa. Cada etapa debe producir algo funcional.

---

## Preguntas que queremos responder

**Meteo → tráfico**: ¿cuánto afecta la lluvia a la velocidad? ¿qué intensidad de lluvia empieza a notarse? ¿depende de la hora, del día, de la zona?

**Meteo → Dbizi**: ¿cuánto cae el uso con lluvia? ¿cuánto tarda el efecto? ¿hay recuperación al escampar?

**Parking → tráfico** (si hay fuente dinámica): ¿la saturación de un parking coincide con más tráfico cercano? ¿patrones compatibles con tráfico de búsqueda de aparcamiento?

**Efecto temporal**: lag entre inicio de lluvia y congestión máxima, duración del impacto, tiempo de recuperación — comparados entre zonas.

**Anomalías**: modelo de comportamiento esperado por (sensor, día tipo, hora, meteo); desviaciones → buscar factor explicativo (lluvia, festivo, evento, incidencia…).
