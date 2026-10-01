# Viajes de madrugada por emparejado inequívoco (2-5 h, 23 noches)

- Eventos nocturnos tras limpieza: 3547 (1741 salidas, 1806 llegadas)
- Parpadeos del feed eliminados (dep→arr misma estación <=6 min): 169
- Pares por unicidad mutua (2-12 min, 8-20 km/h): **24**
- Control con llegadas de 24 h después: 5 pares espurios → señal/ruido ~4.8x
- Correlación distancia-duración: **0.84** · velocidad mediana 13.1 km/h, global 12.9 km/h

## Top pares origen → destino

| origen | destino | viajes | mediana min | km |
|---|---|---|---|---|
| 02 - BRETXA | 45 - XABIER LIZARDI | 1 | 10 | 3.0 |
| 04 - ANDIA | 39 - ZARAUTZ | 1 | 10 | 2.1 |
| 67 - MORAZA 1 | 11 - SAN FRANTZISKO-IPARRAGIRRE | 1 | 4 | 1.0 |
| 66 - ZUHAIZTI PLAZA | 31 - BARCELONA | 1 | 6 | 1.0 |
| 64 - AMETZAGAÑA 47 | 66 - ZUHAIZTI PLAZA | 1 | 4 | 0.7 |
| 61 – SATRUSTEGI 1 | 41 - TOLOSA HIRIBIDEA-KARLOS SANTAMARIA | 1 | 6 | 1.0 |
| 60 - ERREGEZAINTZA 28/ ESCOLTA REAL 28 | 09 - EASO | 1 | 6 | 1.5 |
| 59 - BUENAVISTA | 58 - NORNAHI PLAZATXOA | 1 | 6 | 1.4 |
| 59 - BUENAVISTA | 50- HARROBIETA PLAZATXOA | 1 | 4 | 1.0 |
| 59 - BUENAVISTA | 49- ALTZA KIROLDEGIA | 1 | 4 | 0.5 |
| 47 - HERRERA | 59 - BUENAVISTA | 1 | 4 | 1.3 |
| 01 - UDALETXEA / AYUNTAMIENTO | 40 - TOLOSA HIRIB.-IRAKASLE ESKOLA/MAGISTERIO | 1 | 8 | 2.2 |

## Lectura

- **El método estricto ("silencio en toda la red") no funciona**: entre las 22 y
  la 1 la red nunca calla (~300 eventos/hora a las 23 h) y da 1 par en 43 noches.
- **La madrugada profunda solo existe el fin de semana**: de 2 a 5 h, las noches
  de lunes a viernes tienen ~1 evento en toda la red (la ciudad duerme); las de
  sábado y domingo, 150-450 — la vuelta de la fiesta. Es un hallazgo en sí mismo.
- Con unicidad mutua, ventana 2-12 min y 8-20 km/h salen **24 viajes** con física
  creíble: correlación distancia-duración 0.84, mediana 13 km/h, y el control con
  llegadas de la noche siguiente solo fabrica 5 pares espurios (señal ~5:1, o sea
  ~19 de los 24 son probablemente reales).
- La dirección dominante cuadra con la vuelta a casa: del centro (Bretxa, Andia,
  Udaletxea) hacia barrios (Lizardi, Zarautz, Magisterio) y el corredor
  Herrera-Buenavista-Altza.
- **Límite claro**: cada par origen-destino aparece una sola vez; esto valida el
  concepto pero no da una matriz OD. Para el mapa de a-dónde-va-cada-barrio hará
  falta el enfoque estadístico (correlación con prior de distancia) o meses más
  de sábados.
