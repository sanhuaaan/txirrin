# Reparto óptimo — de describir la red a proponer cómo arreglarla

## La pregunta

> Lo que más molesta de Dbizi como usuario es **llegar a una estación y que esté vacía**.

De ahí sale el objetivo: con el histórico que se va acumulando, estudiar las tendencias de
ocupación y proponer un **reparto hipotético en camión** que minimice las estaciones vacías y
equilibre la red.

Es la primera vez que el proyecto pasa de *entender* a *proponer*. El README ya lo rozaba
("¿la red se recupera sola o necesita redistribución?"), pero sin objetivo concreto.

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

Es **censura por la derecha**, y condiciona todo lo demás:

- Optimizar para "minimizar los ceros observados" **subestima sistemáticamente** la demanda de
  Añorga o Bera Bera, que es la que se quiere satisfacer.
- Tratamiento: estimar la demanda latente de cada estación desde sus propias horas comparables
  **sin censura** (mismo día-tipo, misma hora, cuando sí tenía bicis), o usando estaciones vecinas
  como control.

No es un obstáculo que invalide el proyecto. Es *el* problema metodológico del proyecto, y hay que
tenerlo presente desde el diseño, no descubrirlo al final.

---

## Plan por etapas

Cada etapa produce algo útil por sí sola, aunque el proyecto se pare ahí.

### 1 · Medir el problema — *necesita 3-4 semanas de datos*

Tasa de vacío por **estación × día-tipo × hora**, excluyendo la ventana de cierre y las estaciones
fuera de servicio. Responde "qué estaciones están estructuralmente rotas" sin optimizar nada, y es
probablemente el resultado más presentable del proyecto entero. Usa `holiday` para separar
laborables de festivos.

### 2 · Separar operario de usuarios

Detectar los movimientos de camión: saltos grandes en ventanas cortas, cambios simultáneos y de
signo opuesto en otras estaciones, franja nocturna, magnitudes fuera de lo que explica el flujo
orgánico. Da la **línea base** contra la que comparar: sin ella no se puede afirmar que un plan
propuesto mejore lo que ya se hace.

### 3 · Estimar la demanda censurada

Aquí el proyecto se vuelve serio. Sin esto, las etapas siguientes optimizan sobre una demanda que
se sabe sesgada.

### 4 · Simular y optimizar el reparto

El reparto en sí es un problema de rutas con recogida y entrega (*pickup and delivery*), muy
estudiado y perfectamente tratable con 70 nodos. Es la parte **fácil**: vale exactamente lo que
valga el modelo de demanda que lo alimenta.

---

## Validación

No se puede ejecutar el plan, así que hay que decidir desde el principio cómo se juzga:

- **Backtesting**: ajustar con tres semanas y predecir los ceros de la cuarta.
- **Contra la línea base del operador**: km de camión frente a reducción de vacíos, comparado con
  lo que hace de verdad.
- **Simulación contrafactual**: replay del histórico bajo el plan propuesto. Ojo con la
  circularidad — el simulador usaría el mismo modelo de demanda que se quiere validar.

---

## Qué hace falta y qué ya está

**No hace falta cambiar nada de la captura.** Ya se guardan cada 2 minutos `bikes_available`,
`docks_available`, mecánica/eléctrica, `vehicles_disabled`, `docks_disabled`, `is_installed`,
`is_renting` y `fetched_at`. Es exactamente lo que este análisis necesita, y la cadencia de 2
minutos es la que hace posible detectar camiones. Nada de esto es recuperable a posteriori, así
que era importante que ya estuviera.

**Lo que falta es tiempo.** Varias semanas para los patrones de día-tipo; un par de meses para un
modelo de demanda creíble; y meteorología variada para su interacción con la demanda.

---

## Preguntas abiertas

- ¿El patrón "periferia y cuesta arriba se vacía" se sostiene fuera de agosto?
- ¿Con qué frecuencia redistribuye el operador de verdad? Una noche sin actividad no es un patrón.
- ¿Cuánto dura la recuperación espontánea de una estación vacía, y cuándo no la hay?
- ¿La lluvia agrava el desequilibrio o simplemente reduce el uso de forma uniforme?
- ¿La franja de cierre 00:00-06:00 es fija todo el año o cambia por temporada?
