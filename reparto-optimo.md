# Reparto óptimo — de describir la red a proponer cómo arreglarla

## La pregunta

> Lo que más molesta de Dbizi como usuario es **llegar a una estación y que esté vacía**.

De ahí sale el objetivo, reformulado tras darle una vuelta (2026-08-21): proponer un **reparto
hipotético en camión** que **maximice el tiempo que cada estación pasa en su banda sana** — con
bicis disponibles y con anclajes libres. La formulación inicial («minimizar vacías y equilibrar»)
era peor: ver la sección siguiente.

Es la primera vez que el proyecto pasa de *entender* a *proponer*. El README ya lo rozaba
("¿la red se recupera sola o necesita redistribución?"), pero sin objetivo concreto.

---

## El objetivo: tiempo en banda — y por qué el camión no iguala, contrapesa

**Banda sana** = la estación tiene bicis que coger **y** anclajes donde dejar. Unifica los dos
modos de fallo: en el primer día de datos, 34 estaciones tocaron el cero y **12 se llenaron del
todo**, que es el mismo fallo por el otro lado — no poder devolver.

La consecuencia contraintuitiva: la colocación de las 06:00 que maximiza el tiempo en banda **no
es empezar todas equilibradas**. Dos estaciones de 20 anclajes, ambas al 50% a las 06:00:

| | 06:00 | Deriva típica de mañana | 09:30 |
|---|---|---|---|
| Añorga (periferia) | 10 bicis | pierde ~4/h | **0 — fuera de banda** |
| Boulevard (centro) | 10 bicis | gana ~3/h | **20 — llena, fuera de banda** |

Empezar «equilibrado» las saca a las dos de la banda a media mañana. La colocación óptima es la
contraria a la intuición: Añorga arranca **casi llena** y Boulevard **casi vacía**, cada una
posicionada contra su marea. El camión no reparte equidad: **coloca contrapesos contra la marea
previsible del día**. El histórico no se replica — se usa solo para aprender esa componente
previsible; las capas de meteo y eventos existen para ir moviendo cosas de «imprevisible» a
«previsible».

---

## Lo que ya se ve con 30 horas de datos

Observaciones sobre la ventana **2026-08-20 11:46 → 2026-08-21 tarde** (UTC), ~540 snapshots por
estación. Son indicios, no conclusiones: **un día y medio, en agosto, en temporada vacacional**.

### Las estaciones que se vacían no son aleatorias

| Estación | Capacidad | % del tiempo a 0 |
|---|---|---|
| 52 · Añorga Txiki | 27 | 53,2 |
| 54 · Berio 42 | 15 | 45,5 |
| 55 · Bera Bera | 15 | 42,2 |
| 48 · Larratxo | 15 | 40,6 |
| 16 · Atarizar | 21 | 37,1 |
| 42 · Berio 26 | 19 | 36,7 |
| 22 · Antso Jakituna | 12 | 31,6 |
| 49 · Altza Kiroldegia | 15 | 30,3 |

Altza, Berio, Añorga, Bera Bera: **periferia y cuesta arriba**. La lectura obvia —a confirmar con
más datos— es que las bicis bajan al centro y no vuelven solas. Eso *es* el problema de
redistribución, visible en día y medio.

En total, **178 episodios de vacío**, de 78 minutos de media.

### Tres trampas que hay que esquivar antes de medir nada

**1. Dbizi cierra de 00:00 a 06:00 (hora local).** El 99% de las estaciones reportan
`is_renting = false` en esa franja, frente al 1% en el resto del día. Las bicis siguen ahí (media
de 6,8, igual que de día): no es que se vacíe, es que el servicio está cerrado.

> Cualquier métrica de vacío **debe excluir esa ventana**, o cuenta horas en las que nadie podía
> alquilar. Es también, previsiblemente, la franja en la que operaría el camión.

**2. Dos estaciones están fuera de servicio, no vacías por demanda.** `69 · Náutico` y
`56 · Altza San Martzial` marcan `is_renting = false` de forma permanente — Náutico además con 3
bicis averiadas. Aparecen al 100% de vacío y son ruido: optimizar el reparto hacia ellas sería
mandar bicis donde nadie puede cogerlas.

> Ojo con el filtro fácil: **69 de 70 estaciones tienen `is_renting = false` en algún momento**,
> justamente por el cierre nocturno. Filtrar por "siempre operativa" deja una sola estación. Hay
> que distinguir el cierre de red (todas a la vez, franja fija) de la baja individual (sostenida
> en el tiempo, solo esa estación).

**3. No se detecta camión.** En toda la ventana hay **6 saltos de ≥5 bicis en menos de 6 minutos y
ninguno de ≥8**, y durante las seis horas de cierre la media de la red se quedó plana. Esa noche
el operador no redistribuyó prácticamente nada.

Con una sola noche de agosto no se puede generalizar, pero si el patrón se confirma tiene dos
consecuencias favorables: el **margen de mejora es grande**, y la inferencia de flujos está mucho
**menos contaminada** por movimientos de operario de lo que cabría temer.

---

## El problema difícil: solo se observa inventario, nunca demanda

Cuando una estación está a cero, el feed no dice **cuánta gente llegó y se fue sin bici**. Y eso
ocurre justo en las estaciones que más interesa arreglar: el dato es más ciego precisamente donde
más importa.

Es **censura por la derecha**. Con el objetivo de banda muerde en la **deriva** (flujo neto por
estación y hora), que es justo lo que el contrapeso necesita — y muerde en los dos bordes:

- Mientras una estación está a **cero**, su deriva observada es cero: no puede perder bicis que no
  tiene. Las que más rápido se vacían parecen *más tranquilas* de lo que son.
- Mientras está **llena**, no puede recibir devoluciones: la gente aparca en la de al lado y la
  afluencia real queda oculta, simétricamente.
- Tratamiento: estimar las tasas desde las horas comparables **sin censura** (mismo día-tipo,
  misma hora, con inventario en banda), o usando estaciones vecinas como control.

Hay una asimetría muy conveniente: **la métrica no está censurada**. El tiempo en banda se observa
directamente, así que medir cuán mal está la red (etapa 1) y evaluar un plan es limpio; la censura
solo muerde al **estimar la deriva para planificar** (etapa 3).

No es un obstáculo que invalide el proyecto. Es *el* problema metodológico del proyecto, y hay que
tenerlo presente desde el diseño, no descubrirlo al final.

---

## Plan por etapas

Cada etapa produce algo útil por sí sola, aunque el proyecto se pare ahí.

### 1 · Medir el problema — *necesita 3-4 semanas de datos*

Tiempo fuera de banda —vacía **o llena**— por **estación × día-tipo × hora**, excluyendo la
ventana de cierre y las estaciones fuera de servicio. Responde "qué estaciones están estructuralmente rotas" sin optimizar nada, y es
probablemente el resultado más presentable del proyecto entero. Usa `holiday` para separar
laborables de festivos.

### 2 · Separar operario de usuarios

Detectar los movimientos de camión: saltos grandes en ventanas cortas, cambios simultáneos y de
signo opuesto en otras estaciones, franja nocturna, magnitudes fuera de lo que explica el flujo
orgánico. Da la **línea base** contra la que comparar: sin ella no se puede afirmar que un plan
propuesto mejore lo que ya se hace.

### 3 · Estimar la deriva real (descensurada)

Aquí el proyecto se vuelve serio. No hace falta la matriz de viajes ni «replicar la media» del
histórico: basta la **marea neta por estación y hora**, un objeto mucho más simple. Pero corregida
de censura — o las etapas siguientes optimizan sobre tasas que se saben sesgadas.

### 4 · Simular y optimizar el reparto

Primero la **colocación**: qué configuración a las 06:00 maximiza el tiempo esperado en banda,
dado el perfil de deriva del día. Después la **ruta** que la materializa: recogida y entrega
(*pickup and delivery*), muy estudiado y perfectamente tratable con 70 nodos. Es la parte
**fácil**: vale exactamente lo que valga el modelo de deriva que la alimenta.

---

## Validación

No se puede ejecutar el plan, así que hay que decidir desde el principio cómo se juzga:

- **Backtesting**: ajustar con tres semanas y predecir los ceros de la cuarta.
- **Contra la línea base del operador**: km de camión frente a reducción de vacíos, comparado con
  lo que hace de verdad.
- **Simulación contrafactual**: replay del histórico bajo el plan propuesto. Ojo con la
  circularidad — el simulador usaría el mismo modelo de deriva que se quiere validar.

---

## Qué hace falta y qué ya está

**No hace falta cambiar nada de la captura.** Ya se guardan cada 2 minutos `bikes_available`,
`docks_available`, mecánica/eléctrica, `vehicles_disabled`, `docks_disabled`, `is_installed`,
`is_renting` y `fetched_at`. Es exactamente lo que este análisis necesita, y la cadencia de 2
minutos es la que hace posible detectar camiones. Nada de esto es recuperable a posteriori, así
que era importante que ya estuviera.

**Lo que falta es tiempo.** Varias semanas para los patrones de día-tipo; un par de meses para un
modelo de deriva creíble; y meteorología variada para su interacción con la demanda.

---

## ¿Se afinaría solo al aplicarlo? Sí — con una condición

Aplicado en la realidad, el cálculo de cuántas bicis quitar o poner **mejora con cada iteración**,
y por una razón mejor que «más datos»: **intervenir reduce la censura**. Un buen plan mantiene las
estaciones en banda más horas → más horas con deriva observable → mejores tasas → mejor plan
siguiente. Las intervenciones son además experimentos naturales: una estación que nunca amanece
llena revela su verdadera sangría matinal el primer día que alguien la llena.

La condición: **corregir la censura desde el día uno**. Alimentando el optimizador con los flujos
observados a pelo, el mismo bucle se cierra al revés y fija el sesgo: pocas bicis a Añorga → se
vacía pronto → se observa poco movimiento → «demanda baja» → pocas bicis a Añorga. La
retroalimentación que afina el sistema bien planteado es la que lo bloquea si arranca sesgado.

Dos matices:

- **Nada de «aprendido una vez y listo»**: la deriva no es estacionaria (época del año, meteo,
  obras, cambios en la red). Se re-estima de continuo, pesando más lo reciente.
- **En este proyecto el bucle no se cierra**: sin camión propio, el refinamiento es pasivo — más
  semanas de datos, mejores tablas. La versión de bucle cerrado es la que viviría un operador que
  lo aplicara.

---

## Preguntas abiertas

- ¿El patrón "periferia y cuesta arriba se vacía" se sostiene fuera de agosto?
- ¿Con qué frecuencia redistribuye el operador de verdad? Una noche sin actividad no es un patrón.
- ¿Cuánto dura la recuperación espontánea de una estación vacía, y cuándo no la hay?
- ¿La lluvia agrava el desequilibrio o simplemente reduce el uso de forma uniforme?
- ¿La franja de cierre 00:00-06:00 es fija todo el año o cambia por temporada?
