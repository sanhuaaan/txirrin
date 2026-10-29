# Eléctricas frente a mecánicas (56 días: 39 laborables, 8 sábados, 9 domingos/festivos; horas 6-24)

## Cuánto se usan

- Flota (ancladas de madrugada, red cerrada): **145 eléctricas** y **280 mecánicas** (34 % eléctricas); las eléctricas oscilan entre 88 y 207 según la noche (el operador retira parte a cargar). De día quedan ancladas de media 123 y 267.
- Salidas: **67 % eléctricas** (2387 frente a 1187 al día).
- Rotación: cada eléctrica sale **16.5 veces al día**; cada mecánica, 4.2. En circulación a la vez, de media: 15 % de las eléctricas y 5 % de las mecánicas.
- Cuota eléctrica por tipo de día: domingo/festivo 67 %, laborable 66 %, sábado 70 %.

## ¿La gente las prefiere?

- Con los dos tipos disponibles en la estación, una eléctrica sale **10.0 veces más a menudo** que una mecánica (0.90 frente a 0.09 salidas por bici y hora). Ojo: también refleja que las eléctricas son pocas y cada una rota más.
- Preferencia por hora (laborable): máxima a las 22 h (×11.3), mínima a las 9 h (×7.1).

## Dónde y cuándo faltan

- Tiempo sin eléctricas (con mecánicas disponibles): **27 %** del horario; sin mecánicas (con eléctricas): 15 %.
- Hora más seca de eléctricas en laborable: 23 h (29 % de las estaciones-hora sin ninguna).
- **Demanda eléctrica no atendida** (cota superior): hasta ~**1027 salidas al día** habrían sido en eléctrica si siempre hubiera (30 % de la demanda eléctrica estimada). Parte se hace en mecánica, parte se pierde; es cota superior porque extrapola la tasa de cuando hay eléctricas, que es alta justo porque escasean.

Las que más tiempo pasan sin eléctricas:

| estación | sin eléctricas | eléctricas perdidas/día |
|---|---|---|
| Teresa De Calcuta | 51 % | 26.7 |
| Bermingham | 49 % | 16.3 |
| Zuhaizti Plaza | 48 % | 28.4 |
| San Frantzisko-Iparragirre | 47 % | 31.1 |
| Zabaleta 35 | 47 % | 26.8 |
| Tabakalera | 46 % | 27.5 |
| S.Frantzisko-Galtzada Nagusia | 44 % | 22.9 |
| Nautikoa | 43 % | 16.1 |
| Kristina Infanta | 42 % | 23.0 |
| Segundo Izpizua | 41 % | 25.1 |

## Lectura

- **Las eléctricas son un tercio de la flota y dos tercios de los viajes.** Cada
  eléctrica sale unas 16 veces al día; cada mecánica, 4. Con las dos a mano en la
  misma estación, la eléctrica se lleva diez veces más a menudo por bici; la
  preferencia es más fuerte de noche (×11 a las 22 h) y más débil en la punta de
  las 9 h, cuando se coge lo que hay.
- **Las eléctricas casi no paran**: de madrugada hay unas 145 ancladas (el
  operador retira parte a cargar: entre 88 y 207 según la noche); de día quedan
  123 de media y a las 18 h una de cada cuatro está circulando. Las mecánicas
  nunca pasan del 7 % en circulación.
- **Faltan donde más se piden**: el 27 % del horario una estación está sin
  eléctricas teniendo mecánicas (frente al 15 % al revés). Las peores están en el
  llano: Teresa de Calcuta, Bermingham, Zuhaizti, Iparragirre, Zabaleta,
  Tabakalera, cada una más del 40 % del tiempo sin ninguna.
- **Cota superior de demanda eléctrica no atendida: ~1.000 salidas al día** (30 %
  de la demanda eléctrica estimada). Es cota superior porque extrapola la tasa de
  cuando hay eléctricas, inflada justamente por la escasez; parte de esa gente se
  lleva una mecánica.
- Ruido conocido del feed: ~6 % de los movimientos eléctricos se revierten en
  menos de 6 minutos y ~6 % son reclasificaciones (una eléctrica pasa a contar
  como mecánica sin cambiar el total, seguramente por batería). Las
  reclasificaciones están descontadas; las reversiones no.
- **Para el operador**: con esta preferencia, cada eléctrica adicional vale por
  varias mecánicas en viajes; y el reparto de eléctricas hacia el llano (donde
  se agotan) es un criterio tan importante como el de bicis totales hacia la
  cuesta.

## ¿Y si el camión repartiera eléctricas y mecánicas por separado? (2026-10-29)

Se probó un reparto óptimo por tipo (tasas nocturnas por tipo en `rates.json`,
simulación con eléctricas y mecánicas separadas, sustitución de la mitad de quien
no encuentra eléctrica, objetivo: viajes perdidos). Con la demanda bien estimada
(eléctrica = salidas totales − demanda mecánica propia, 74 % del total), el
resultado en un laborable a las 06:00:

- 30 bicis en 12 estaciones: viajes perdidos 1.133 → 1.094 (−3 %).
- 100 bicis en 24 estaciones: 1.133 → 1.080, y el tiempo con estaciones vacías
  empeora (26 % → 29 %), porque prefiere llevar eléctricas al llano que bicis a
  la cuesta.

**Conclusión: el cuello de botella eléctrico es el tamaño de la flota, no dónde
está.** Hay unas 3.300 salidas eléctricas de demanda al día para ~145
eléctricas; recolocarlas apenas cambia nada. El modo por tipo se retiró de la web
y del cálculo nocturno (commit 6714648, revertido después); el reparto web sigue
por bicis totales, que sí da mejoras claras. Primer intento descartado por otro
motivo: corregir la censura de las eléctricas sin descontar a los sustitutos de
las mecánicas inflaba la demanda eléctrica hasta el 95 %.
