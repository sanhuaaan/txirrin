# Calibración del planificador (test 2026-09-29 → 2026-10-12, 14 días)

Brier = error cuadrático de la probabilidad (menor es mejor); 'mejora' es frente a la media de red por tipo de día y hora (no sabe qué estación es).

| entrenamiento | k | objetivo | Brier estación | Brier red | mejora |
|---|---|---|---|---|---|
| toda la historia | 0 | vacía | 0.0662 | 0.0788 | +16 % |
| toda la historia | 0 | llena | 0.0102 | 0.0091 | -13 % |
| toda la historia | 0 | sin eléctricas | 0.1178 | 0.1442 | +18 % |
| toda la historia | 2 | vacía | 0.0651 | 0.0788 | +17 % |
| toda la historia | 2 | llena | 0.0096 | 0.0091 | -5 % |
| toda la historia | 2 | sin eléctricas | 0.1160 | 0.1442 | +20 % |
| toda la historia | 5 | vacía | 0.0651 | 0.0788 | +17 % |
| toda la historia | 5 | llena | 0.0091 | 0.0091 | -0 % |
| toda la historia | 5 | sin eléctricas | 0.1165 | 0.1442 | +19 % |
| desde el curso | 0 | vacía | 0.0711 | 0.0789 | +10 % |
| desde el curso | 0 | llena | 0.0113 | 0.0091 | -24 % |
| desde el curso | 0 | sin eléctricas | 0.1261 | 0.1436 | +12 % |
| desde el curso | 2 | vacía | 0.0664 | 0.0789 | +16 % |
| desde el curso | 2 | llena | 0.0098 | 0.0091 | -7 % |
| desde el curso | 2 | sin eléctricas | 0.1189 | 0.1436 | +17 % |
| desde el curso | 5 | vacía | 0.0660 | 0.0789 | +16 % |
| desde el curso | 5 | llena | 0.0092 | 0.0091 | -1 % |
| desde el curso | 5 | sin eléctricas | 0.1190 | 0.1436 | +17 % |

## Calibración de la mejor variante (toda la historia, k=2)

Para cada tramo de probabilidad predicha: qué fracción del tiempo pasó de verdad.

| predicho | vacía (real, n) | llena (real, n) | sin eléctricas (real, n) |
|---|---|---|---|
| 0.00–0.05 | 0.03 (6243) | 0.01 (15178) | 0.02 (99) |
| 0.05–0.15 | 0.10 (5783) | 0.05 (1874) | 0.13 (1443) |
| 0.15–0.30 | 0.21 (3674) | 0.08 (489) | 0.26 (4283) |
| 0.30–0.50 | 0.37 (1486) | 0.09 (44) | 0.44 (6787) |
| 0.50–0.70 | 0.52 (384) | — | 0.59 (4126) |
| 0.70–1.00 | 0.55 (15) | — | 0.77 (847) |

Días de test por tipo: {'dom': 3, 'lab': 9, 'sab': 2}
