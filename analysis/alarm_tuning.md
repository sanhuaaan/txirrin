# Afinado de la alarma 'vacía en 30 min' (transiciones, 485 vaciados en 11102 casos)

## Barrido del umbral θ (alarma si q10 <= θ)

| θ | precisión | recall | | θ (punto) | precisión | recall |
|---|---|---|---|---|---|---|
| 0.0 | 0.30 | 0.19 | | 0.0 | 0.00 | 0.00 |
| 0.5 | 0.24 | 0.64 | | 0.5 | 0.57 | 0.04 |
| 1.0 | 0.16 | 0.84 | | 1.0 | 0.25 | 0.35 |
| 1.5 | 0.13 | 0.89 | | 1.5 | 0.19 | 0.64 |
| 2.0 | 0.11 | 0.95 | | 2.0 | 0.17 | 0.78 |
| 3.0 | 0.09 | 0.98 | | 3.0 | 0.12 | 0.90 |

- Mejor F1: θ=0.50 → precisión 0.24, recall 0.64

## ¿Umbral por cluster? (elegido en train, evaluado en test)

- Global θ=0.50: precisión 0.24, recall 0.65
- Por cluster {-1: 0.5, 0: 0.5, 1: 0.5, 2: 0.25, 3: 0.5}: precisión 0.24, recall 0.61

## Dónde acierta (θ=0.50)

| segmento | precisión | recall | vaciados |
|---|---|---|---|
| cluster -1 | 0.33 | 0.33 | 6 |
| cluster 0 | 0.17 | 0.52 | 73 |
| cluster 1 | 0.21 | 0.65 | 103 |
| cluster 2 | 0.25 | 0.65 | 109 |
| cluster 3 | 0.27 | 0.68 | 194 |
| madrugada 0-7 | 0.23 | 0.36 | 42 |
| mañana 7-13 | 0.25 | 0.73 | 128 |
| tarde 13-20 | 0.26 | 0.65 | 294 |
| noche 20-24 | 0.07 | 0.52 | 21 |

## Lectura

- La curva completa confirma el techo: **con recall útil (>0.5), la precisión no
  pasa de ~0.25** se mire por donde se mire. θ=0.5 sobre q10 (p 0.24, r 0.64)
  es el punto de trabajo razonable; subir el umbral compra recall a precio ruinoso.
- **Personalizar el umbral por cluster no aporta** (test: 0.24/0.61 vs 0.24/0.65
  global). Con 485 vaciados no hay grasa para segmentar — descartado con datos.
- **Dónde sí y dónde no**: de día funciona (mañana p 0.25 / r 0.73; tarde 0.26 /
  0.65); de noche es inútil (20-24 h: p 0.07) — mejor silenciarla fuera de 7-20 h.
- Para subir la precisión hace falta señal nueva, no otro umbral: covariables
  (lluvia, hora, festivo) en la segunda ronda del forecast, y guardar más
  cuantiles (q20-q40) en el próximo backtest — aquí solo había q10/q90.
- **Veredicto de despliegue**: vale como capa visual de "riesgo" en el timelapse
  (una falsa alarma pintada de ámbar no molesta); no vale para notificaciones.
