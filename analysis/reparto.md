# Reparto óptimo, primera vuelta (38 laborables, 8 sábados, 9 domingos/festivos; horas 6-24 h)

## Etapa 1 · Cuánto tiempo falla la red

| tipo de día | vacía | llena | fuera de banda | horas/día por estación |
|---|---|---|---|---|
| domingo/festivo | 12.8 % | 2.6 % | **15.4 %** | 2.8 h |
| laborable | 13.1 % | 2.0 % | **15.1 %** | 2.7 h |
| sábado | 13.3 % | 2.2 % | **15.6 %** | 2.8 h |

Las que más fallan en laborable:

| estación | vacía | llena | fuera de banda |
|---|---|---|---|
| Altza San Martzial Plaza | 55 % | 0 % | **55 %** |
| Txapillo | 41 % | 0 % | **41 %** |
| Altza Kiroldegia | 40 % | 0 % | **40 %** |
| Berio 42 | 35 % | 0 % | **35 %** |
| Gabriel Celaya Plaza | 35 % | 0 % | **35 %** |
| Bera Bera | 33 % | 0 % | **33 %** |
| Berio 26 | 31 % | 0 % | **31 %** |
| Pio Baroja 20 | 30 % | 0 % | **30 %** |
| Errondogaina | 26 % | 0 % | **26 %** |
| Pagola-Lugaritz | 25 % | 0 % | **25 %** |
| Andoain | 22 % | 0 % | **22 %** |
| Larratxo | 22 % | 0 % | **22 %** |

## Etapa 3 · La marea, corregida de censura

- Salidas estimadas en laborable: 66/día por estación (+15 % sobre las observadas: lo que las estaciones vacías dejaron de prestar).
- Dónde más demanda se pierde por vacío (salidas/día no atendidas): Berio 42 22, Karmengo Andre Maria 19, Errondogaina 19, Txapillo 18, Pio Baroja 20 16.

## Etapa 4 · Colocación a las 06:00 (laborable)

- **Validación del simulador**: con el stock real de las 06:00 predice 22.4 % fuera de banda; lo observado es 15.1 % (correlación entre estaciones 0.75). Sobreestima: el modelo de fluido exagera la deriva. Las mejoras son relativas, no una promesa.
- Flota en juego: 419 bicis a las 06:00 entre 70 estaciones.
- Fuera de banda, simulado: **22.4 % → 5.9 %** con el reparto óptimo (74 % menos).
- Sábado: 21.9 % → 9.8 %.
- Domingo/festivo: 17.6 % → 2.4 %.

Movimientos de 2 o más bicis (61 estaciones, 159 bicis cambian de sitio):

| estación | hoy a las 06:00 | óptimo | mover | fuera de banda hoy → óptimo |
|---|---|---|---|---|
| Antzieta | 18 | 2 | -16 | 7 % → 28 % |
| Tranbia | 14 | 2 | -12 | 43 % → 14 % |
| Nornahi Plazatxoa | 12 | 4 | -8 | 0 % → 0 % |
| Cortázar Arkitektoak | 9 | 2 | -7 | 3 % → 0 % |
| Karmengo Andre Maria | 6 | 0 | -6 | 33 % → 42 % |
| Zuhaizti Plaza | 6 | 1 | -5 | 0 % → 0 % |
| Bera Bera | 1 | 8 | +7 | 67 % → 0 % |
| Pagola-Lugaritz | 5 | 14 | +9 | 60 % → 0 % |
| Gabriel Celaya Plaza | 3 | 13 | +10 | 79 % → 0 % |
| Sagastieder | 6 | 17 | +11 | 65 % → 0 % |
| Pio Baroja 20 | 2 | 14 | +12 | 76 % → 1 % |
| Txapillo | 2 | 15 | +13 | 88 % → 22 % |
| Munto | 4 | 18 | +14 | 65 % → 0 % |
| Andoain | 5 | 20 | +15 | 54 % → 0 % |

Ruta orientativa (vecino más cercano, línea recta): 61 paradas, ~36.3 km, empezando en Andoain.

## Lectura

- **Etapa 1, el dato presentable**: la red pasa el **15 % del tiempo de servicio
  fuera de banda** (2,7 h al día por estación), casi todo por vacío (13 %), no
  por lleno (2 %). Y es estructural: Altza San Martzial está sin bicis más de
  la mitad del día laborable; Txapillo, Altza Kiroldegia, Berio 42, Gabriel
  Celaya y Bera Bera, más de un tercio. Todas cuesta arriba.
- **Etapa 3, la demanda que no se ve**: descensurar las horas vacías añade un
  15 % de salidas a la red. Las estaciones que más préstamos pierden por estar
  vacías (Berio 42, Karmengo Andre Maria, Errondogaina, Txapillo, Pio Baroja:
  16-22 salidas/día cada una) son demanda real que hoy se queda en la acera.
- **Etapa 4, el reparto**: con la misma flota (419 bicis a las 06:00), mover
  ~160 bicis del llano (centro, Gros, Amara) a la periferia alta reduce el
  tiempo fuera de banda simulado de 22 % a 6 %. La dirección es inequívoca y
  cuadra con todo lo anterior; la magnitud es optimista.
- **Por qué optimista**: el simulador exagera la deriva (predice 22 % donde se
  observa 15 %) y trabaja con el día medio, sin la variabilidad entre días ni la
  lluvia. Además la DP acepta empeorar alguna estación (Antzieta 7→28 %,
  Karmengo 33→42 %) si la red gana en conjunto; una versión con tope de
  empeoramiento por estación sería más vendible.
- **La ruta** (61 paradas, ~36 km en línea recta) es solo un orden de magnitud:
  un camión real lleva 20-30 bicis por viaje y no haría todas las paradas.
- **Siguiente vuelta** (con lluvia variada, hacia noviembre): tasas condicionadas
  a meteo, simulación por réplica de días reales en vez de tasas medias, tope de
  empeoramiento y capacidad del camión.

## En la web (2026-10-13)

El botón *Reparto* del timelapse ejecuta este mismo modelo en el navegador con la
marea de `rates.json` (la VM la recalcula cada noche con `build_rates.py`, mismo
método que arriba). Diferencias respecto a esta primera vuelta offline, todas
nacidas de la observación de que el óptimo "puro" movía el 40 % de la flota:

- **Hora elegible** (06-23 h) con ventana de 24 h (la noche cerrada no mueve
  nada), y opción de partir del estado real de ahora en vez del stock típico.
- **Precio por bici movida y por parada** (una parada cuesta como 3 bicis), con
  un único multiplicador que la web busca por bisección para respetar dos topes:
  bicis a mover y estaciones a visitar.
- **Suelo de 1 bici** por estación (la marea media no ve los días malos) y
  **ninguna parada por una sola bici** (mueve 0 o >=2).
- **Curva de rendimientos decrecientes**, laborable 06:00 con datos reales:
  22 bicis en 11 estaciones 24 → 18 %; 44 en 20, → 14 %; 165 en 64, → 6 %.
  La mitad de la mejora máxima se compra con una ruta de 11 estaciones.

## Simulador "Un día con reparto" (2026-10-13)

Artifact interactivo (`viz/reparto_dia.tpl.html` + `rates.json` embebido;
publicado en https://claude.ai/artifact/EcQHHkXF41eGXZgqTvKUEE, privado): el mismo
día corriendo dos veces, sin y con reparto, con el camión recorriendo su ruta,
la curva de estaciones fuera de banda y contadores de horas sin bici, viajes
perdidos y estaciones vacías al cerrar. Mismo modelo que la web, más tres
palancas que la web no tiene. Lo que enseñó, laborable desde las 06:00,
40 bicis y 12 estaciones por ronda salvo que se diga otra cosa:

| escenario | horas de estación sin bici | vacías al cerrar | viajes perdidos |
|---|---|---|---|
| hoy | 249 | 14 | 660 |
| 1 ronda (06:00) | 179 | — | 577 |
| 3 rondas fijas (06, 12, 18) | 135 | 9 | 426 |
| 3 rondas antes de las subidas (06, 09, 13) | 113 | 7 | 383 |
| 4 rondas fijas, 80/20 (06, 12, 18, 22) | 57 | 0 | 194 |
| 4 rondas antes de las subidas, 80/20 (06, 09, 13, 16) | 19 | 0 | 65 |
| +100 bicis de flota, sin reparto | 172 | — | 494 |
| +100 anclajes, 1 ronda | 177 | — | 572 |
| +100 bicis y 4 rondas 80/20 | 23 | 0 | 83 |

- **Una ronda matutina no arregla el día**: la periferia drena sin parar y lo
  repuesto a las 06:00 se ha ido a mediodía. Las curvas con y sin reparto
  convergen por la tarde.
- **Rondas programadas antes de las subidas de vacías** (inicio de los tramos
  en que más crece el número de estaciones vacías sin reparto, mirando 3 h por
  delante) ganan a los horarios fijos en 5 de 6 casos: el drenaje es de mañana y
  mediodía; a las 18:00 o 22:00 se llega tarde, aunque sirva para cerrar a cero.
- **Cerrar el día sin ninguna estación vacía** cuesta 4 rondas de ~40 bicis en
  ~20 estaciones (~160 bicis/día): un camión a jornada completa.
- **La flota es la palanca grande** (+100 bicis sin camión ≈ 3 rondas diarias) y
  se multiplica con el reparto; **los anclajes solos no sirven**: la red tiene
  417 bicis para 1.325 anclajes (31 % de ocupación), sobran huecos.
- Heurística del horario auto: sencilla y a veces falla (sábado, 3 rondas:
  junta dos rondas y deja la noche); una búsqueda exhaustiva de horas la
  corregiría a cambio de segundos de cálculo por cambio de mando.
