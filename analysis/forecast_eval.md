# Backtest zero-shot (184 orígenes cada 3 h, 70 estaciones, semanas lectivas sep-2026)

## MAE (bicis)

| model       |   30min |   1h |   2h |
|:------------|--------:|-----:|-----:|
| naive24h    |    3.65 | 3.63 | 3.66 |
| persistence |    0.94 | 1.39 | 2.11 |
| profile     |    1.15 | 1.68 | 2.33 |
| timesfm     |    0.93 | 1.37 | 2    |

## Cobertura banda p10-p90 (objetivo 0.80)

| model   |   30min |   1h |   2h |
|:--------|--------:|-----:|-----:|
| timesfm |    0.79 | 0.79 | 0.79 |

## 'Vacía en 30 min' (verdad: <=0.5 bicis; predicción: pred <=0.5)

| modelo | precisión | recall | precisión (transiciones) | recall (transiciones) |
|---|---|---|---|---|
| naive24h | 0.29 | 0.29 | 0.09 | 0.22 |
| persistence | 0.69 | 0.72 | 0.00 | 0.00 |
| profile | 0.75 | 0.39 | 0.35 | 0.05 |
| timesfm | 0.74 | 0.68 | 0.57 | 0.04 |

(transiciones: estaciones que no estaban vacías en el origen; ahí la persistencia no puede acertar.)

## La banda baja como alarma de vaciado (transiciones, 30 min)

| regla | precisión | recall | alarmas |
|---|---|---|---|
| mediana <= 0.5 | 0.57 | 0.04 | 30 |
| q10 <= 0.5 | 0.24 | 0.64 | 1.315 |
| q10 = 0 | 0.31 | 0.20 | 320 |

485 vaciados reales en 11.102 casos de transición. La mediana casi nunca avisa; el
cuantil bajo recupera 2 de cada 3 vaciados a cambio de 3 falsas alarmas por acierto.
El umbral es un mando: recall vs ruido.

## Lectura

- TimesFM zero-shot **empata con la persistencia** en MAE a 30 min-1 h y le gana
  ~5 % a 2 h. El perfil histórico y el naive de 24 h quedan claramente detrás.
- Su valor real no es el punto sino la **incertidumbre**: cobertura p10-p90 de 0.79
  con objetivo 0.80, calibración casi perfecta sin haber visto jamás una bici.
- Predecir vaciados que aún no han empezado es difícil para todos; solo la banda
  baja de TimesFM ofrece un mando precision/recall utilizable.
