# Donostia Bike Intelligence

## 1. Idea del proyecto

Proyecto personal de **ingeniería y análisis de datos centrado en la red de bicicletas públicas Dbizi de Donostia-San Sebastián**.

El objetivo es construir un histórico de la evolución de la red y estudiar cómo diferentes factores externos afectan a su comportamiento:

- meteorología;
- calendario laboral;
- eventos;
- incidencias y obras;
- y, potencialmente, cualquier otra fuente que permita explicar cambios en la movilidad ciclista.

La pregunta central:

> **¿Podemos entender el comportamiento normal de la red Dbizi y detectar y explicar cuándo se comporta de forma anómala?**

No pretende ser una plataforma comercial ni institucional. Donostia será nuestro **laboratorio real de experimentación con datos de movilidad**.

> **Dbizi es el objeto de estudio; el resto de fuentes son contexto.**

---

## 2. Por qué Dbizi

Motivación técnica y personal: es una fuente dinámica que representa comportamiento real de movilidad urbana, y un servicio usado habitualmente. Interesa entender:

- cómo se comporta la red;
- qué estaciones tienen problemas recurrentes;
- cómo afecta el tiempo;
- qué ocurre durante eventos;
- cuándo y dónde aparecen desequilibrios;
- cómo evoluciona a lo largo del día y de la semana.

La intención no es representar datos en un mapa:

> **El objetivo es tratar Dbizi como un sistema dinámico que podemos observar, modelizar y analizar.**

Además, la Fase 0 (ver [`fase-0-fuentes.md`](fase-0-fuentes.md)) confirmó que es, con diferencia, la mejor fuente abierta de la ciudad — mientras que el tráfico urbano directamente no se publica.

---

## 3. Fuentes de datos

### 🚲 Dbizi — fuente principal ✅ validada

**GBFS oficial, público, sin autenticación** (PBSC/Lyft):

```text
https://sansebastian.publicbikesystem.net/customer/gbfs/v3.0/gbfs.json
```

- `station_information`: **70 estaciones** con lat/lon, dirección, capacidad.
- `station_status`: bicis y anclajes disponibles, estado (`is_renting`, `is_returning`), `last_reported` en segundos, **desglose mecánica vs. eléctrica** (`vehicle_types_available`).
- TTL 21–30 s → tiempo casi real.
- **Sin histórico** → uno de los primeros componentes será un **collector periódico** que construya el nuestro:

```text
GBFS Dbizi
    │
    │ cada X minutos (configurable)
    ▼
Collector
    │
    ▼
PostgreSQL (crudo + normalizado)
    │
    ▼
histórico propio
```

### 🌧️ Meteorología — Euskalmet ✅ validada

Principal fuente externa para explicar cambios de comportamiento. Variables: precipitación, temperatura, humedad, viento, presión…

- **Histórico**: zips anuales gratuitos, granularidad **10 min**, desde 2003.
- **Tiempo real**: API `api.euskadi.eus/euskalmet` con key gratuita (JWT RS256); sandbox sin auth para desarrollar.
- **Matiz clave**: la única estación de Donostia con **precipitación es C017 Miramón** (43.2868, -1.97121). Santa Clara (C007) apoya con viento/temperatura. Para una ciudad de este tamaño, basta para el MVP.

Relación espacial estación Dbizi → estación meteo más cercana vía PostGIS (con una sola estación de lluvia, trivial de inicio).

**Preguntas**: ¿cómo afecta la lluvia al uso/disponibilidad? ¿hay umbral de precipitación? ¿efecto del viento y la temperatura? ¿cuánto tarda en aparecer el efecto? ¿cuánto tarda la red en recuperarse?

### 📅 Calendario laboral

Variable fundamental para distinguir comportamiento normal: día de la semana, laborable/festivo, vacaciones, mes, estación, puentes. Un lunes 08:30 se compara con otros lunes 08:30, no con un domingo. Implementación: **tabla de festivos de Gipuzkoa rellenada a mano** (~14 filas/año), no un módulo.

### 🎫 Eventos ✅ validada (tres piezas)

Una de las fuentes más interesantes para explicar anomalías. Cubierta con (detalle en el anexo de [`fase-0-fuentes.md`](fase-0-fuentes.md)):

1. **API Kulturklik** (`api.euskadi.eus/culture/events/v1.0/events/byMonth/{y}/{m}/byMunicipality/20/82`, sin key) — agenda cultural completa, Semana Grande, Illumbe, Kursaal. Ojo: municipio **82** (NORA), coordenadas = centroide → tabla propia `venue → coords`, y **la API purga el pasado** → cosecha diaria.
2. **TheSportsDB** (key `3`, Real Sociedad `idTeam 133724`) — partidos en Anoeta con hora local, filtrando `strVenue = "Reale Arena"`.
3. **Scraper del Kursaal** (`/es/tipo/reuniones/`) — solo congresos, que no salen en Kulturklik.

```text
evento → zona afectada → estaciones Dbizi cercanas → cambio de comportamiento
```

**Preguntas**: ¿picos de demanda? ¿qué estaciones? ¿cuándo empieza y cuánto dura el efecto? ¿estaciones que se vacían vs. que acumulan? ¿la red se recupera sola o necesita redistribución?

### 🚧 Incidencias y obras ✅ fuente parcial validada

Para explicar cambios locales: obras, cortes, restricciones. La API de tráfico de Euskadi publica **incidencias en tiempo real con coordenadas** (~30-80k/año desde 2021, sin key) — verificado en Fase 0. Vía PostGIS: incidencia → estaciones a < X metros → ¿cambia su comportamiento durante el periodo?

### Otras fuentes

Regla de admisión:

> **Una fuente nueva debe permitir responder una pregunta nueva sobre el comportamiento de Dbizi.**

Candidatas: **parkings de Donostia** (plazas libres en vivo vía `getParkings.xsp`, ya validada en Fase 0 — ¿elección modal coche/bici según meteo?), Dbus, calidad del aire, peatones, infraestructura ciclista, y **tráfico si algún día vuelve a publicarse** (los sensores urbanos existen pero nunca han emitido; la GI-20 cortó en nov-2024).

No se incorporarán datasets solo por aumentar volumen.

---

## 4. Decisiones de diseño

Recortes deliberados (cada uno con su condición de reapertura):

1. **Una sola aplicación con un scheduled job por fuente** — no un servicio por fuente. *Se separa si un collector necesita ciclo de vida propio.*
2. **PostgreSQL + PostGIS y nada más.** Sin TimescaleDB/ClickHouse/Kafka hasta necesidad medida. *Se reevalúa si una agregación tarda segundos con índices correctos.*
3. **Exploración en notebook (pandas + folium/plotly) o Grafana** antes que dashboard Vue + API propia. *Dashboard cuando haya algo que enseñar a otros.*
4. **Guardar siempre el crudo** (JSONB) además de lo normalizado — las APIs cambian de formato.
5. **ML aplazado** hasta tener histórico y una pregunta que lo justifique.

---

## 5. Arquitectura conceptual

```text
                    ┌──────────────┐
                    │  GBFS DBIZI  │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  Collector   │  (una app, un job por fuente)
                    └──────┬───────┘
                           │
        ┌──────────────────▼──────────────────┐
        │        PostgreSQL + PostGIS         │
        └──────────────────┬──────────────────┘
                           │
            ┌──────────────┼──────────────┬─────────────┐
            ▼              ▼              ▼             ▼
       Euskalmet      Calendario       Eventos     Incidencias
            └──────────────┴──────┬───────┴─────────────┘
                                  ▼
                             ANALYTICS
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
                Patrones      Anomalías     Predicción
                                  │
                                  ▼
                     (notebook / Grafana → más adelante REST API + Vue)
```

---

## 6. Modelo de datos

Separación **estación** (estático) / **medición** (serie temporal) para no duplicar; `geom` PostGIS; `raw` JSONB con la respuesta original.

```text
dbizi_station(id, name, geom, capacity, source)
dbizi_measurement(station_id, timestamp, bikes_available, docks_available,
                  mechanical_available, electric_available, status, raw jsonb)

weather_station(id, name, geom, altitude, source)
weather_measurement(station_id, timestamp, temperature, precipitation, humidity,
                    wind_speed, pressure, raw jsonb)

event(id, name, start_time, end_time, geom, type, source)
incident(id, type, description, start_time, end_time, geom, source)
holiday(date, name)
```

PostGIS permite: estación meteo más cercana, estaciones afectadas por incidencia/evento, agrupación por barrios (GeoJSON de barrios disponible en el CKAN municipal), distancias. El proyecto trabaja esencialmente con **espacio + tiempo → comportamiento**.

---

## 7. Construcción del histórico

Captura del estado completo de la red cada pocos minutos (frecuencia configurable; el TTL del feed es ~30 s, así que 1–5 min da resolución de sobra):

```text
Estación A
12:00 → 8 bicicletas
12:05 → 7
12:10 → 6
12:15 → 4
12:25 → 0
```

Esto construye lo que la API no da: la evolución temporal de la red.

---

## 8. Primer objetivo: describir el comportamiento normal

Antes de predecir, saber qué es "normal". Perfil por estación × día-tipo × hora, y comparación observado vs. esperado:

```text
Estación X, 18:00
Esperado: 12 bicicletas · Real: 2 · Desviación: -10
```

Esa desviación es la base de la detección de anomalías.

---

## 9. Detección y explicación de anomalías

Anomalía = comportamiento significativamente distinto del esperado: estación vacía cuando no toca, saturada cuando no toca, o con una evolución distinta a la habitual aunque tenga bicis.

Para cada anomalía, consultar el contexto:

```text
¿Llovía? ¿Viento? ¿Festivo? ¿Evento? ¿Obra/incidencia cerca? ¿Qué hacen las vecinas?
```

Sin afirmar causalidad automáticamente: el objetivo es generar **hipótesis explicativas basadas en datos**.

---

## 10. Análisis de la red

No solo estación a estación: la red completa. Estaciones que se vacían rápido, que acumulan, nodos importantes, desequilibrios, patrones de redistribución, zonas con comportamiento propio, estaciones que tocan 0% o 100% de forma recurrente → **problemas estructurales de la red**.

### Inferencia de movimientos (especulativa)

Con frecuencia alta de captura se pueden inferir flujos entre estaciones (A pierde 3, B gana 3). Información **inferida, no observada**: la contaminan redistribución del operador, estaciones llenas/vacías y movimientos simultáneos. Si resulta fiable, podría construirse un grafo temporal de movilidad ciclista. No es objetivo del MVP.

---

## 11. Meteorología y dinámica temporal

No solo `lluvia sí/no`: intensidad, duración, tiempo desde inicio/fin de la lluvia, temperatura, viento. Fenómenos a medir:

```text
inicio de lluvia → lag → cambio de comportamiento → máximo impacto → fin → recuperación
```

Métricas: `weather_impact_lag`, `maximum_impact`, `impact_duration`, `recovery_time` — comparables entre estaciones y zonas.

---

## 12. Visualización

Fase notebook/Grafana primero (decisión 3). El dashboard, cuando llegue: mapa (estaciones, disponibilidad, anomalías, eventos, incidencias, meteo), timeline para recorrer el histórico, gráficas por estación, y comparaciones tipo *lunes lluvioso vs. lunes seco* o *día normal vs. día con evento*.

---

## 13. Machine Learning (aplazado)

Cuando haya histórico y pregunta que lo justifique:

- **Predicción**: bicis disponibles a +15/+30 min por estación (hora, día, histórico, meteo, eventos, vecinas).
- **Predicción de saturación**: ¿qué estaciones tienen riesgo de quedarse a 0 (o llenarse) en 30 min? — esto tendría incluso utilidad práctica directa.

---

## 14. Stack

- **Backend**: Java + Spring Boot, una app con scheduled jobs (collectors) y, más adelante, REST.
- **BD**: PostgreSQL + PostGIS. (TimescaleDB/ClickHouse solo si el dolor aparece.)
- **Exploración**: notebook / Grafana. **Frontend** Vue cuando haya audiencia.
- **Ingestión**: Spring Scheduler. Colas/Kafka/streams solo si surge necesidad real — no antes.

---

## 15. Fases

```text
1. Ingestión         → "Consigo datos de Dbizi y construyo histórico"   ← EN MARCHA: git-scraping desde 2026-08-20 (ver infraestructura.md)
2. Observación       → "Veo cómo se comporta la red"
3. Contextualización → "Incorporo meteorología y calendario"
4. Explicación       → "Incorporo eventos e incidencias"
5. Anomalías         → "Detecto lo que se sale de lo normal"
6. Análisis          → "Busco factores que lo expliquen"
7. Predicción        → "Anticipo el comportamiento de la red"
8. Experimentación   → "Nuevas fuentes = nuevas preguntas"
```

Cada fase debe producir algo funcional. No es necesario llegar a la última.

## 16. MVP

1. Collector capturando el GBFS periódicamente → PostgreSQL (crudo + normalizado).
2. Estado actual + histórico propio creciendo.
3. Gráficas temporales por estación (notebook).
4. Cargar meteo de Miramón (histórico 10-min ya descargable).
5. Comparar días y condiciones meteorológicas.

Primera pregunta que debe poder responder el sistema:

> **¿Cómo cambia el comportamiento de Dbizi a lo largo del día y cómo se relaciona con las condiciones meteorológicas?**

---

## 17. Qué hace interesante al proyecto

Trabajar con un sistema real, dinámico e imperfecto: APIs, ingestión periódica, construcción de históricos, series temporales, PostGIS, estadística, anomalías, análisis de redes, inferencia de movimientos, ML, visualización. Y el problema clásico de la ingeniería de datos:

> **Los datos que necesitamos no existen exactamente como nos gustaría, así que tenemos que construirlos y decidir cómo interpretarlos.**

## 18. Reparto óptimo

El objetivo que da al proyecto un para qué, más allá de describir: usar el histórico para proponer
un **reparto hipotético en camión** que maximice el tiempo que cada estación pasa en su banda
sana (con bicis que coger y anclajes donde dejar). Documento propio en
[`reparto-optimo.md`](reparto-optimo.md), con lo que ya se ve en los primeros datos (la periferia
cuesta arriba se vacía; Dbizi cierra de 00:00 a 06:00; no se detecta camión), el problema
metodológico de fondo (solo se observa inventario, nunca demanda) y el plan por etapas.

## 19. Ideas para jugar

Sin objetivo analítico — porque sí:

- **Timelapse isométrico de la ciudad** ✅ *primera versión*: las 70 estaciones como columnas 3D que crecen y decrecen al ritmo de los snapshots. Se construye con `scripts/build_timelapse.py` (stdlib pura: dos CSV de Postgres dentro, HTML autocontenido fuera) sobre `viz/timelapse.tpl.html` y la geometría de barrios ya simplificada en `viz/donostia-barrios.json`. El HTML generado no se versiona: `./scripts/build_timelapse.py stations.csv meas.csv` lo rehace.
  - Sin deck.gl al final: se dibuja a canvas con una proyección isométrica propia (~40 líneas), porque así el HTML no depende de ningún CDN y se puede compartir tal cual.
  - **Cámara de torno**: arrastrar gira e inclina (de casi perfil a casi cenital), la rueda acerca anclando al puntero, shift+arrastra o botón derecho mueve, y en táctil hay pinza. Doble clic o `0` reinicia; `[` `]` giran, flechas arriba/abajo inclinan, `+` `-` acercan. Una barandilla impide perder la ciudad de vista. La escala se ajusta al círculo que contiene la ciudad y no al bbox de cada ángulo: así no crece y mengua mientras arrastras. El orden del pintor se recalcula por frame porque la profundidad depende del ángulo, y hay brújula porque bajo isométrica el norte no es una rotación de pantalla.
  - **Relieve**: la ciudad es una maqueta. EU-DEM a 25 m muestreado a 50 m (`scripts/fetch_dem.py` → `viz/donostia-dem.json`), tinta hipsométrica oscura por bandas de 20 m y sombreado por pendiente con la luz fija respecto a quien mira; exageración vertical ×2,2 para que Urgull, Igeldo y Ulia compitan con columnas de 46 m por bici. El mar no sale del DEM (media Amara está a cota 0): es lo conectado al borde norte por inundación sobre la ortofoto PNOA (`scripts/fetch_ortho.py`), así entran bahía, Santa Clara y ría y no los tejados; se pinta como polígono suavizado (contorno de las celdas + Chaikin), porque celda a celda la costa salía en escalera. El agua va en verde azulado apagado, lejos a propósito del azul de las columnas llenas. El **Urumea** va como vector de OpenStreetMap (`scripts/fetch_river.py`): a 50 m por celda un río no cabe en el relieve. Mientras arrastras el terreno se pinta a 100 m y al soltar, a 50.
  - Se probó colorear cada celda desde la ortofoto, como pixel art, y se descartó: la textura bajo las columnas las hacía más difíciles de leer. El suelo es fondo; las columnas, figura.
  - **Lo que falla, señalado**: las estaciones vacías o llenas *ahora* llevan su nombre (rojo/azul; solo ellas, las 70 serían ruido), la llena además una tapa con el borde encendido, y cada una deja una **huella** en el suelo que crece con las horas acumuladas de fallo en la ventana (techo a 300 m): al final del día se ve dónde duele sin mover el reproductor. Sombra en la base para anclar las columnas al relieve.
  - **Las otras fuentes, en la página**: junto al reloj, la meteo de esa hora (temperatura, lluvia en mm/h o «seco», viento); bajo la fecha, el tipo de día (laborable, fin de semana o festivo con su nombre); en el panel, una fila «Agenda del día · n ›» que abre un modal con las citas de ese día (hora, tipo, nombre, recinto; Kulturklik no publica hora de comienzo, se rescata de la descripción cuando la menciona y si no se dice «hora no publicada»), sin las exposiciones de semanas, que no mueven bicis un día concreto. Y sobre el reproductor, una **franja** con la lluvia en barras y la temperatura en línea alineada con el scrubber: se ve *cuándo* llovió respecto a la marea. Los eventos no van al mapa: falta la tabla `venue → coords` (pendiente de Fase 0).
  - **Vista de entrada**: norte arriba (giro −45°, inclinación 54°, más cenital que la isométrica porque con el norte arriba a 35° el fondo sale aplastado), maqueta centrada en el hueco libre entre cabecera, leyenda, panel y reproductor. La escala no cambia al girar.
  - **Altura** = bicis disponibles. **Color** = rampa divergente rojo↔gris↔azul: los dos extremos son fallos —ni bici que coger, ni sitio donde dejarla— y el equilibrio es lo silencioso. Los polos están validados para daltonismo contra el fondo oscuro.
  - **En vivo**: https://storage.googleapis.com/cosas-con-datos-en-dbizi-viz/index.html — `publish_viz.sh` regenera el JSON cada 5 min en la VM y lo sube a un bucket público; la página lo recarga cada 2 min. Sin abrir puertos y sin exponer la base de datos. El artefacto de Claude sigue siendo una foto congelada, porque su CSP no permite ningún `fetch` externo.
  - Lo que se ve con 28 h de datos: el total de la red apenas oscila un 6%, pero 34 de 70 estaciones tocan el cero y 12 se llenan del todo. La historia es la **redistribución**, no el volumen.
  - Pendiente, y es lo que pedía la idea original: *lunes lluvioso vs. lunes seco* lado a lado. Acotar el `WHERE ts` de la consulta ya permite generar cada día por separado; falta tener dos lunes comparables y la vista doble.

## 20. Posicionamiento

> **Estoy construyendo un sistema para estudiar cómo se comporta la red Dbizi de Donostia: un histórico propio de sus estaciones cruzado con meteorología, calendario, eventos e incidencias para detectar patrones, anomalías y posibles explicaciones.**

La ausencia de datos de tráfico no bloquea el proyecto; si algún día vuelven a publicarse, se incorporan como una dimensión más. El proyecto empieza como **laboratorio de movilidad ciclista** y puede crecer hacia un análisis más amplio de movilidad urbana.
