# Txirrin — Donostia Bike Intelligence

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

**De dónde sale esta URL.** No es una API escondida: es **GBFS** (*General Bikeshare Feed Specification*), el estándar abierto que mantiene [MobilityData](https://gbfs.org) (nacido en la North American Bikeshare Association en 2015) y que casi todos los sistemas de bici pública publican para que Google Maps, Citymapper o Transit muestren las bicis disponibles. Por diseño es público y sin clave. Dbizi lo opera PBSC Urban Solutions (hoy parte de Lyft), y PBSC sirve el GBFS de todos sus sistemas con el mismo patrón de dominio, `<ciudad>.publicbikesystem.net/customer/gbfs/v3.0/gbfs.json`, igual que Barcelona, Montreal o Buenos Aires; `gbfs.json` es el índice que lista los demás feeds. Está listado en el [catálogo oficial de sistemas GBFS](https://github.com/MobilityData/gbfs/blob/master/systems.csv) (`systems.csv`, una fila por ciudad) y enlazado desde Open Data Euskadi como dato abierto de movilidad.

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
- **Complemento en marcha**: [Open-Meteo](https://open-meteo.com) (`api.open-meteo.com`, API documentada, gratuita y sin clave para uso no comercial), horaria, para cubrir el desfase de ~2 meses con que Open Data Euskadi publica los XML mensuales de Euskalmet. Es la que alimenta la meteo del timelapse.
- **Matiz clave**: la única estación de Donostia con **precipitación es C017 Miramón** (43.2868, -1.97121). Santa Clara (C007) apoya con viento/temperatura. Para una ciudad de este tamaño, basta para el MVP.

**¿Por qué dos fuentes de meteo?** Hacen papeles distintos y ninguna puede hacer el de la otra:

| | Euskalmet C017 | Open-Meteo |
|---|---|---|
| Qué es | **Observación**: pluviómetro real en Miramón | **Modelo** interpolado a un punto: «realidad según un modelo» |
| Paso | 10 min | horario |
| Llega | con **~2 meses de retraso** (XML mensuales) | **al día**, hasta la hora actual |
| Histórico | desde 2003 | lo que se pida (archivo, ~2 días por detrás) |
| Riesgo | ninguno en el dato; solo el retraso | puede perderse un chubasco local |
| Sirve para | entrenar y validar; la verdad del suelo | el timelapse en vivo y la predicción como covariable |

Lo que se guarda de Open-Meteo **no es predicción**: es el análisis del modelo para horas ya pasadas. El tramo futuro (`forecast_days=1`) se descarga y se descarta; archivarlo es el pendiente que apunta [`reparto-optimo.md`](reparto-optimo.md). El timelapse se alimenta solo de Open-Meteo. Nunca se mezclan por descuido: `interval_minutes` marca la serie y los mm son acumulados del intervalo.

**Pendiente que justifica tener las dos**: validar Open-Meteo contra C017. Hoy no se solapan ni un día (C017 hasta el 30 de junio, Open-Meteo desde el 1 de julio); `openmeteo.sh 2026-01-01 2026-06-30` daría seis meses de solape para medir cuánto se equivoca el modelo en Donostia por hora y por umbral de lluvia. Si acertara lo suficiente, entonces sí se podría prescindir de una.

Relación espacial estación Dbizi → estación meteo más cercana vía PostGIS (con una sola estación de lluvia, trivial de inicio).

**Preguntas**: ¿cómo afecta la lluvia al uso/disponibilidad? ¿hay umbral de precipitación? ¿efecto del viento y la temperatura? ¿cuánto tarda en aparecer el efecto? ¿cuánto tarda la red en recuperarse?

### 📅 Calendario laboral

Variable fundamental para distinguir comportamiento normal: día de la semana, laborable/festivo, vacaciones, mes, estación, puentes. Un lunes 08:30 se compara con otros lunes 08:30, no con un domingo. Implementación: **tabla de festivos de Gipuzkoa rellenada a mano** (~14 filas/año), no un módulo.

### 🎫 Eventos ✅ validada (tres piezas)

Una de las fuentes más interesantes para explicar anomalías. Cubierta con (detalle en el anexo de [`fase-0-fuentes.md`](fase-0-fuentes.md)):

1. **API Kulturklik** (`api.euskadi.eus/culture/events/v1.0/events/byMonth/{y}/{m}/byMunicipality/20/82`, sin key; publicada en el [portal de APIs del Gobierno Vasco](https://api.euskadi.eus), que es también donde está la de Euskalmet) — agenda cultural completa, Semana Grande, Illumbe, Kursaal. Ojo: municipio **82** (NORA), coordenadas = centroide → tabla propia `venue → coords`, y **la API purga el pasado** → cosecha diaria.
2. **Deporte y pruebas populares** ✅ implementado (`scripts/harvest_sports.py` → tabla `event`, con hora y coordenadas del recinto; cron diario). Kulturklik es agenda cultural: ni deporte, ni hora, ni recinto geolocalizado, y lo que más mueve la red es Anoeta lleno o la Behobia. Tres entradas: **openfootball** (GitHub, sin clave) para el calendario completo de Liga, con fechas provisionales hasta que LaLiga confirma; **TheSportsDB** (clave pública `3`; Real Sociedad `133724`, Gipuzkoa Basket `135084`) para el próximo y el último partido con hora confirmada —el calendario de temporada es de pago—, que pisan al provisional de su día; y las pruebas populares: regatas de la Concha (primer y segundo domingo de septiembre) y Behobia (segundo domingo de noviembre) se **derivan por regla** para el año en curso y el siguiente, sin mantenimiento; Clásica y maratón, que varían, van en `data/eventos-populares.csv` a mano (una línea al año). Se buscó una fuente estructurada y no la hay: Kulturklik no tiene deporte, el CKAN de Donostia no tiene agenda, Wikidata se queda en ediciones de 2015/2025 sin fecha exacta y las webs oficiales (y ProCyclingStats) bloquean scrapers. Solo partidos en casa. En el timelapse salen en la agenda con hora y, mientras duran, como anillo ámbar sobre el recinto. La tabla `event` es, de paso, el `venue → coords` que pedía la Fase 0.
3. **Scraper del Kursaal** (`/es/tipo/reuniones/`) — solo congresos, que no salen en Kulturklik. Pendiente.

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

### Primeros resultados (2026-08-25, 5 días de datos)

Perfil 24 h por estación (ocupación normalizada por capacidad, hora local, laborable/finde) y k-means sobre la *forma* de la curva (media restada, 48 puntos). Código: [`sql/profiles.sql`](sql/profiles.sql) → `data/profiles.csv` → [`analysis/profiles.py`](analysis/profiles.py) → `analysis/profiles.png` + `data/profiles_clusters.csv`. Con k=4 y sin darle ninguna información geográfica, el clustering reproduce el mapa funcional de la ciudad:

| Clúster | n | Forma laborable | Finde | Dónde |
|---|---|---|---|---|
| C0 destino/centro | 14 | vacía de noche, se llena 7-12 h, pico 19 h | llenado retrasado a mediodía | Bretxa, Andia, Urdaneta, Ayuntamiento, Zabaleta, Gros |
| C2 residencial | 15 | la inversa: llena de noche, se vacía 7-12 h, mínimo 19 h, vuelve 21-24 h | igual, más suave | Amara, Egia, Intxaurrondo, Antiguo alto (Morlans, Podavines, Herrera, Antzieta, Ametzagaña) |
| C1 residencial suave / ocio | 18 | ligera bajada diurna | se llenan por la mañana y se vacían a mediodía | Bermingham, Tabakalera, Tranbia, Añorga, Altza |
| C3 plana / ruidosa | 22 | sin patrón | sin patrón | Ibaeta-campus, Altza kiroldegia, Bera Bera, Errondo |
| plana (apartada) | 1 | >70 % del tiempo vacía o llena | | Náutico |

Lecturas: la señal residencial/destino ya está en 5 días; C3 es el clúster "trabajo/universidad" que en agosto no existe y debería partirse en octubre (rehacer y comparar es en sí un resultado); C0/C2 son la base para elegir gemelos en el simulador de estación fantasma (§19). Para refrescar: relanzar el `COPY` en la VM, bajar el CSV y ejecutar el script (`python3 analysis/profiles.py [k]`).

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

Con frecuencia alta de captura se pueden inferir flujos entre estaciones (A pierde 3, B gana 3). Información **inferida, no observada**: la contaminan redistribución del operador, estaciones llenas/vacías y movimientos simultáneos.

**Redistribución del operador (comprobado 2026-08-25, 5 días):** no hay evidencia de rebalanceo con furgoneta en Dbizi. Saltos de ≥5 bicis en 2 min: 36 en toda la semana (≈5/día en 70 estaciones), sin pares −N/+N entre estaciones ni horario fijo; los saltos de ±3-4 se concentran a las 16-21 h (grupos de usuarios). Los de madrugada son 1-2 en la semana. Conclusión provisional: las bicis van donde las llevan los usuarios y solo hay retirada de averiadas (`vehicles_disabled`), lo que hace más relevante el flujo neto vs. altitud (§18). Si resulta fiable, podría construirse un grafo temporal de movilidad ciclista. No es objetivo del MVP.

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

### Hecho (2026-10-01): modelos fundacionales de series temporales, zero-shot

Evaluado TimesFM 3.0 (200M, CPU del portátil, venv `uv` con Python 3.11) sobre 6 semanas de datos:
backtest de 184 orígenes cada 3 h en las semanas lectivas de septiembre, 70 estaciones, series a 15 min,
contexto de 4 días, horizonte 2 h, contra persistencia / naive 24 h / perfil+persistencia.
Resultados en `analysis/forecast_eval.md` (script `analysis/forecast_eval.py`, export `sql/forecast_series.sql`):

- **MAE**: TimesFM 0,93 / 1,37 / 2,00 bicis a 30 min / 1 h / 2 h; la persistencia 0,94 / 1,39 / 2,11.
  Empate a corto, ~5 % de ventaja a 2 h. Perfil y naive 24 h, claramente peor.
- **Calibración**: cobertura p10-p90 de 0,79 (objetivo 0,80) sin haber visto jamás la red. Es el valor real.
- **"Vacía en 30 min"** sobre transiciones (no estaba vacía en el origen): la mediana solo caza el 4 %;
  la alarma por cuantil bajo (q10 <= 0,5) recupera el **64 % con precisión 0,24** — el umbral es un mando
  recall/ruido que ningún baseline tiene.

Conclusión: el punto no justifica producción; la banda sí justifica una segunda ronda.

El plan original, para contexto:

- **Serie**: `bikes_available` por estación remuestreado a 10 min; predecir ocupación normalizada (0-1) y desnormalizar; recortar cuantiles a `[0, capacidad]`. Descartar ventanas con hueco (`fetched_at`).
- **Backtest**: ventana deslizante, cada hora en punto × 70 estaciones × N días (~23k predicciones con 2 semanas), horizontes 10/30/60/120 min, separado laborable/finde y por clúster de §8.
- **Baselines obligatorias**: persistencia (lo que hay ahora), naive estacional (ayer/media laborables a esa hora), perfil + persistencia (valor actual + variación del perfil medio en la próxima hora). Si el fundacional no bate a la tercera, no vale la pena.
- **Métricas**: MAE de la mediana en bicis por horizonte; cobertura del intervalo p10-p90 (calibración); y la operativa: "vacía en 30 min sí/no" → precisión/recall contra lo ocurrido.
- **Entregable**: `analysis/forecast_eval.py` (~120 líneas, `pip install chronos-forecasting`), tabla de resultados y un gráfico de una tarde en Bera Bera con el abanico de cuantiles y el real encima.
- **Segunda ronda** (con meses y lluvia): TimesFM/Moirai con covariables (meteo, festivo). **Producción** solo si la evaluación lo justifica: cron en el portátil que sube un JSON al bucket `-viz` y el timelapse pinta "vacía en 30 min"; Cloud Run como alternativa; nunca la VM.
- Ventaja del dato: sin rebalanceo del operador (§10) la serie es limpia. Lo que se aprende: a qué horizonte deja de servir, si los cuantiles están calibrados y en qué tipo de estación gana al naive.

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
metodológico de fondo (solo se observa inventario, nunca demanda), el plan por etapas y la
versión continua del problema: tiempo hasta el fallo por estación a cualquier hora, el origen que
«sale gratis» (la estación que va a llenarse, no la más cercana) y la cascada como ruta de
horizonte rodante. Incluye el mismo cálculo sin camión, como incentivo a los usuarios al estilo
*Bike Angels* de Citi Bike.

## 19. Ideas para jugar

Sin objetivo analítico — porque sí:

- **Timelapse isométrico de la ciudad — «Txirrin»** ✅ (*txirrin*: el timbre de la bici, en euskera): las 70 estaciones como columnas 3D que crecen y decrecen al ritmo de los snapshots. Se construye con `scripts/build_timelapse.py` (stdlib pura: dos CSV de Postgres dentro, HTML autocontenido fuera) sobre `viz/timelapse.tpl.html` y la geometría de barrios ya simplificada en `viz/donostia-barrios.json`. El HTML generado no se versiona: `./scripts/build_timelapse.py stations.csv meas.csv` lo rehace.
  - Sin deck.gl al final: se dibuja a canvas con una proyección isométrica propia (~40 líneas), porque así el HTML no depende de ningún CDN y se puede compartir tal cual.
  - **Cámara de torno**: arrastrar gira e inclina (de casi perfil a casi cenital), la rueda acerca anclando al puntero, shift+arrastra o botón derecho mueve, y en táctil hay pinza. Doble clic o `0` reinicia; `[` `]` giran, flechas arriba/abajo inclinan, `+` `-` acercan. Una barandilla impide perder la ciudad de vista. La escala se ajusta al círculo que contiene la ciudad y no al bbox de cada ángulo: así no crece y mengua mientras arrastras. El orden del pintor se recalcula por frame porque la profundidad depende del ángulo, y hay brújula porque bajo isométrica el norte no es una rotación de pantalla.
  - **Relieve**: la ciudad es una maqueta. EU-DEM a 25 m muestreado a 50 m (`scripts/fetch_dem.py` → `viz/donostia-dem.json`), tinta hipsométrica oscura por bandas de 20 m y sombreado por pendiente con la luz fija respecto a quien mira; exageración vertical ×2,2 para que Urgull, Igeldo y Ulia compitan con columnas de 46 m por bici. El mar no sale del DEM (media Amara está a cota 0): es lo conectado al borde norte por inundación sobre la ortofoto PNOA (`scripts/fetch_ortho.py`), así entran bahía y ría y no los tejados (Santa Clara, a cota 0 en el DEM de 50 m, se la tragaba: va como polígono de OSM pintado encima); se pinta como polígono suavizado (contorno de las celdas + Chaikin), porque celda a celda la costa salía en escalera. El agua —mar, ría y río, una sola tinta— va en azul-gris oscuro con un filo tenue, lejos a propósito del azul de las columnas llenas. El **Urumea** va como vector de OpenStreetMap (`scripts/fetch_river.py`): a 50 m por celda un río no cabe en el relieve. Mientras arrastras el terreno se pinta a 100 m y al soltar, a 50. La **cobertura del suelo** también es de OpenStreetMap (`scripts/fetch_landcover.py`): manchas urbanas, parques y bosques como polígonos drapeados sobre el relieve con una veladura apagada (gris cálido, verde corto, verde oscuro), los viales principales como un hilo claro, las calles secundarias más tenues, el tren a trazos y la huella de los edificios de más de 1 200 m² (766 de los 8 000 de OSM: los pequeños no se verían) como manchas un punto más claras; así Amara y el Antiguo se leen como ciudad y Ulia e Igeldo como monte sin que el suelo compita con las columnas. Se probó antes rasterizarlo por celda de 50 m y salía a bloques, el mismo defecto del pixel art.
  - Se probó colorear cada celda desde la ortofoto, como pixel art, y se descartó: la textura bajo las columnas las hacía más difíciles de leer. El suelo es fondo; las columnas, figura.
  - **Viajes estimados**: de captura en captura (2 min), cada bici que falta en una estación es una salida y cada una que aparece, una llegada; un viaje son las dos. Se cuenta antes de cuadricular a 5 min (un +1 y un −1 en el mismo frame se anulan) los saltos de 6 o más bicis de golpe se descartan como camión de reparto y la bici que pasa a averiada no cuenta como salida. Va en el panel como acumulado desde el inicio de la ventana y en la tira del reproductor como área de viajes/hora. Es una cota alta: cuenta también la bici sacada y devuelta en la misma estación, y el reparto de pocas bicis cada vez. En un domingo de agosto salen ~3 500 en 24 h.
  - **Bicis averiadas**: `vehicles_disabled` del feed, bicis ancladas que el sistema da por rotas: ocupan anclaje y no se pueden coger. Van en el tooltip («3 / 16 bicis (+ 2 averiadas) · equilibrada») y en el panel como total de la red; no en la barra (se probó como segmento encima y era ruido). Una estación con 0 disponibles y bicis rotas ancladas cuenta como vacía: no hay nada que coger. El dato tiene historia: de jueves a domingo (20–23 de agosto) el total pasó de 28 a 69; el fin de semana las averías se acumulan y nadie las retira. Con él se corrige el conteo de viajes: una bici que pasa a averiada no es una salida (baja el conteo un 7 %).
  - **Feed parado, avisado**: `data.json` lleva `meta` con el último `ts` del feed, cuándo lo capturamos (`fetched_at`) y lo último que reportó una estación. Si capturamos pero el feed repite el mismo instante más de 10 min, «Última captura» se pone en ámbar y dice «feed de Dbizi parado desde las HH:MM»; si no capturamos desde hace 15 min, «sin capturas». Sin esto, datos viejos parecerían frescos.
  - **Lo que falla, señalado**: las estaciones vacías o llenas *ahora* llevan su nombre (rojo/azul; solo ellas, las 70 serían ruido), la llena además una tapa con el borde encendido, y cada una deja una **huella** en el suelo: un disco que, mientras la estación sigue sin bicis, crece (50 + 75·√h metros, techo 300) y se enciende (del 7 % al 25 % de opacidad en 4 h); cuando recupera, encoge y se apaga con una constante de tiempo que se acorta con la raíz de las bicis que tenga (150 min con una bici, 67 con cinco, 47 con diez): recuperar con una bici es precario y la huella tarda en irse. Para la llena, igual en azul y al revés (cuenta anclajes libres). Cerrada no suma ni resta. Sombra en la base para anclar las columnas al relieve. Las **cerradas o averiadas** (`is_installed` falso, o ni `is_renting` ni `is_returning`) van en gris con la tapa discontinua y etiqueta «cerrada», tienen su contador y no cuentan como vacías ni dejan huella: Náutico llevaba días saliendo como «vacía» y en realidad está fuera de servicio. Van en ámbar, no en gris: el gris se confundía con el suelo. Cuando cierra la red entera (≥90 %) se indica una vez junto al reloj. Horario de Dbizi: de 06:00 a 00:00 de lunes a viernes; sábados, domingos y festivos, 24 h.
  - **Las otras fuentes, en la página**: junto al reloj, la meteo de esa hora (temperatura, lluvia en mm/h o «seco», viento); bajo la fecha, el tipo de día (laborable, fin de semana o festivo con su nombre); en el panel, una fila «Agenda del día · n ›» que abre un modal con las citas de ese día (hora, tipo, nombre, recinto; Kulturklik no publica hora de comienzo, se rescata de la descripción cuando la menciona y si no se dice «hora no publicada»), sin las exposiciones de semanas, que no mueven bicis un día concreto. Y sobre el reproductor, una **franja** con la lluvia en barras y la temperatura en línea alineada con el scrubber: se ve *cuándo* llovió respecto a la marea. Los eventos no van al mapa: falta la tabla `venue → coords` (pendiente de Fase 0).
  - **Vista de entrada**: norte arriba (giro −45°, inclinación 54°, más cenital que la isométrica porque con el norte arriba a 35° el fondo sale aplastado), maqueta centrada en el hueco libre entre cabecera, leyenda, panel y reproductor. La escala no cambia al girar.
  - **Altura** = bicis disponibles. **Color** = rampa divergente rojo↔gris↔azul: los dos extremos son fallos —ni bici que coger, ni sitio donde dejarla— y el equilibrio es lo silencioso. Los polos están validados para daltonismo contra el fondo oscuro.
  - **En vivo**: https://storage.googleapis.com/cosas-con-datos-en-dbizi-viz/index.html — `publish_viz.sh` regenera el JSON cada 5 min en la VM y lo sube a un bucket público; la página lo recarga cada 2 min. Sin abrir puertos y sin exponer la base de datos. El artefacto de Claude sigue siendo una foto congelada, porque su CSP no permite ningún `fetch` externo.
  - Lo que se ve con 28 h de datos: el total de la red apenas oscila un 6%, pero 34 de 70 estaciones tocan el cero y 12 se llenan del todo. La historia es la **redistribución**, no el volumen.
  - Pendiente, y es lo que pedía la idea original: *lunes lluvioso vs. lunes seco* lado a lado. Acotar el `WHERE ts` de la consulta ya permite generar cada día por separado; falta tener dos lunes comparables y la vista doble.

- **Simulador de estación fantasma** (idea 2026-08-24, para cuando haya meses de histórico): el usuario pincha un punto del mapa y se simula cómo funcionaría una estación ahí. Reformulación que lo hace viable: aprender qué hace que las 70 estaciones se comporten como se comportan *en función de su ubicación*, y evaluar esa función en el punto nuevo. Rasgos de ubicación, casi todos ya en la despensa: renta/demografía por barrio (CKAN), altitud y pendiente (el DEM del timelapse), distancias a centro/playas/campus/tren, bidegorris, **frecuencia de bus por corredor (GTFS estático de Dbus)**, presión de parking (`getParkings.xsp`), POIs de OSM.
  - **v1 «estación gemela»** (sin entrenar nada): k estaciones existentes más parecidas por rasgos → sus perfiles típicos (hora/día-tipo, sensibilidad a lluvia) como pronóstico, con el porqué («se parece a Amara por X»). Visual: una columna fantasma respirando junto a las reales en Txirrin.
  - **Credibilidad**: validación leave-one-out — predecir cada estación existente desde las otras 69 y publicar el error («acierta el perfil con ±X bicis; toma la nueva con esa sal»).
  - **Verdades incómodas que la UI debe decir**: n=70 (modelos simples o vecinos, nada de ML fino), vemos disponibilidad y no demanda (la estación vacía no registra los alquileres que no pudieron pasar — demanda censurada), y una estación nueva canibaliza a las vecinas y cambia el rebalanceo (la v1 lo ignora y lo declara).
  - **Rasgos que más moverían la aguja** (criterio: cobertura total del mapa, coste bajo, no redundante; con n=70 los rasgos escasos estorban): **empleo/actividad por zona** (la renta dice quién vive ahí; los puestos de trabajo, quién va — Eustat establecimientos o POIs de OSM por categoría en radio), **el desnivel bien usado** (del DEM ya presente: coste de pedaleo del entorno + desequilibrio altimétrico — la gente baja en bici y sube en otra cosa, una estación en alto tiene salida neta crónica), **posición en la propia red** (distancia/capacidad de vecinas y su estrés observado: vecinas que tocan cero a diario = demanda insatisfecha heredable), y **centralidad del bidegorri en su grafo** (corredor troncal vs apéndice, no mera cercanía).
  - **Descartado como palanca**: la dinámica de parkings — 16 parkings concentrados en el centro dejan el rasgo vacío en dos tercios del mapa, y donde existe lo tapan los rasgos estáticos; su sitio es la pregunta de elección modal, no esta. Si algún día hay histórico, el LOO mide su aporte y decide.
  - **Cerrados con llave** (carpeta de peticiones): contadores DFG de peatones/bici (PDF), Strava Metro (convenio, no API), MUGI por parada.
  - **Y lo que gana a todo**: más meses de histórico propio (estaciones del año, lluvia real, curso escolar) — un octubre lluvioso enseña más al modelo que cualquier POI. Las fuentes son una tarde cada una; el tiempo no se compra.

## 20. Posicionamiento

> **Estoy construyendo un sistema para estudiar cómo se comporta la red Dbizi de Donostia: un histórico propio de sus estaciones cruzado con meteorología, calendario, eventos e incidencias para detectar patrones, anomalías y posibles explicaciones.**

La ausencia de datos de tráfico no bloquea el proyecto; si algún día vuelven a publicarse, se incorporan como una dimensión más. El proyecto empieza como **laboratorio de movilidad ciclista** y puede crecer hacia un análisis más amplio de movilidad urbana.

---

## 21. Cuaderno de a bordo

La vista única de qué se ha analizado, qué corre solo y qué espera. Cada análisis
tiene su informe completo en `analysis/`.

### Hecho

| fecha | pregunta | veredicto | informe |
|---|---|---|---|
| 2026-08-25 | ¿Hay rebalanceo del operador? | No: la serie es comportamiento puro de usuarios (§10) | — |
| 2026-08-25 | ¿Qué personalidad tiene cada estación? | 4 clusters: el mapa funcional de la ciudad emerge solo (§8) | `profiles.py` |
| 2026-08-25 | ¿Funciona bien el servicio? | Periferia alta >50 % vacía por las tardes; centro saturado al mediodía; eléctricas ausentes en el llano | `service_level.md` |
| 2026-09-14 | ¿Se nota el inicio de curso? | Sí: +3 % viajes laborables, red más vaciada de día, despierta el corredor universitario | `curso.md` |
| 2026-10-01 | ¿Predice un modelo fundacional zero-shot? | Empata con la persistencia en MAE; su valor es la banda p10-p90 calibrada (0.79/0.80) | `forecast_eval.md` |
| 2026-10-01 | ¿Se pueden trazar viajes de madrugada? | 24 viajes validados (13 km/h, r=0.84); la madrugada solo existe el finde — la vuelta de fiesta es medible | `night_trips.md` |
| 2026-10-01 | ¿Hasta dónde llega la alarma de vaciado? | Techo de precisión ~0.25 con recall útil; por cluster no aporta; de noche inútil | `alarm_tuning.md` |

### Corriendo solo (todo dentro de la VM gratuita)

- **Collector**: snapshot GBFS cada 2 min a Postgres, sin un día perdido desde el 2026-08-20.
- **Contexto**: meteo horaria (Open-Meteo), festivos y cosecha de eventos.
- **Timelapse**: `data.json` cada 5 min al bucket; la web con paso 5 min/30 min/1 h.

**Principio vigente**: en producción solo lo que quepa en la e2-micro gratuita.
El portátil vale para análisis puntuales, no para servicios.

### En el cajón, para un hipotético upgrade del sistema

- **Capa de riesgo "vacía en 30 min"** (construida y probada el 2026-10-01, parada
  por decisión de infra): `scripts/risk_forecast.py` + unidades systemd
  (`txirrin-risk.{service,timer}`) corren TimesFM cada 15 min (7-20 h) y suben
  `risk.json`; el timelapse pinta anillos ámbar en el directo y se auto-apaga si
  el JSON caduca (>25 min). Necesita ~2 GB de RAM para torch: no cabe en la
  e2-micro. Candidatos de upgrade: VM mayor, Cloud Run por invocación, o
  cualquier máquina siempre encendida. Reactivar en un portátil:
  `systemctl --user enable --now txirrin-risk.timer`. Cada pasada deja línea en
  `data/risk_log.jsonl` para auditar la precisión real en producción.

### Cola de experimentos (y a qué dato espera cada uno)

| experimento | espera a | cuándo |
|---|---|---|
| **Reparto óptimo, etapa 1**: tiempo fuera de banda por estación × día-tipo × hora (§18, [`reparto-optimo.md`](reparto-optimo.md)) | nada — pedía 3-4 semanas y hay 6 | **lista ya** |
| Elasticidad a la lluvia | días mojados y secos comparables de otoño | finales de octubre |
| **Pintxo-pote, segunda pasada** (`analysis/pintxopote.py`): confirmar el jueves de Gros (Gran Vía + Bermingham ×1.5), el miércoles de Pio Baroja/Txapillo y el lunes de Sagastieder con el doble de semanas, y validación nativa del mapa | más ocurrencias de cada día de la semana (ahora solo ~6) | finales de octubre |
| Matriz origen-destino estadística (prior de distancia) | más sábados acumulados | noviembre |
| Clustering estacional (re-retrato de la ciudad) | otoño completo en la base | noviembre |
| Forecast 2ª ronda: covariables (lluvia, hora, festivo) + más cuantiles | lo mismo que la lluvia | noviembre |
| Auditoría real de la alarma (`risk_log.jsonl` vs base) | que la capa vuelva a correr unas semanas | tras el upgrade |
| Reparto óptimo, etapa 3 (deriva descensurada con covariables) y etapa 4 (colocación + ruta) | un par de meses de datos y meteo variada; la etapa 2 ya está resuelta (no hay camión, §10) | noviembre en adelante |
