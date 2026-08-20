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

| Fuente | Datos | URL |
|--------|-------|-----|
| 🚗 Open Data Euskadi | Tráfico: aforos, intensidad, velocidad, incidencias | <https://opendata.euskadi.eus/> |
| 🌧️ Euskalmet | Meteo: precipitación, temperatura, viento… (con histórico en Open Data Euskadi) | <https://www.euskalmet.euskadi.eus/> |
| 🅿️ Open Data Donostia | Aparcamientos (estático seguro; dinámico por confirmar) | <https://www.donostia.eus/datosabiertos/> |
| 🚲 Dbizi | Bici pública: estaciones, disponibilidad. **Comprobar si expone GBFS** | <https://www.dbizi.eus/> |
| 📅 Calendario | Festivos de Gipuzkoa: tabla rellenada a mano (~14 filas/año) | — |

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

## Fase 0 — validar las fuentes (una tarde)

Todo el proyecto depende de qué publique realmente Open Data Euskadi para Donostia. Antes de modelar nada:

1. Script que pegue a la API de tráfico y vuelque el JSON crudo.
   - ¿Hay aforos urbanos o solo carreteras forales / N-1?
   - ¿Hay histórico o solo estado actual?
   - ¿Granularidad temporal? ¿Coordenadas de sensores?
2. Lo mismo con Euskalmet (el histórico existe en Open Data Euskadi — pata resuelta).
3. Comprobar si Dbizi expone feed GBFS. Si sí, **Dbizi + lluvia puede ser mejor primer MVP que tráfico + lluvia**: señal enorme, dato limpio, ingestión trivial.

Si el tráfico solo ofrece datos actuales, el collector debe arrancar cuanto antes: se necesitan meses de histórico propio para responder nada sobre lluvia.

---

## MVP v1 — tráfico (o Dbizi) + meteorología

1. Obtener histórico disponible de tráfico y meteo.
2. Normalizar timestamps y localizar sensores/estaciones.
3. Asociar cada sensor de tráfico a su estación meteorológica más cercana (PostGIS).
4. Agregaciones horarias.
5. Analizar en notebook el efecto de la lluvia sobre velocidad e intensidad.

> ¿Cómo varía la velocidad/intensidad del tráfico cuando llueve?

Comparando siempre días comparables (lunes 08:30 con lluvia vs. lunes 08:30 seco, no vs. domingo).

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
