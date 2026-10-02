# ¿Detectan las bicis el pintxo-pote? (llegadas 19-23 h, lunes-viernes, 30 tardes)

Exceso LOCAL: llegadas del día, deflactadas por el factor de red de ese día (el viernes sube en todas partes y eso no es pintxo-pote), frente al resto de diarios; se exige repetirse en >=70 % de las semanas.

| estación | día | llegadas esa tarde | resto de tardes | exceso | semanas que se repite |
|---|---|---|---|---|---|
| 12 - S.FRANTZISKO-GALTZADA NAGUSIA / GRAN VÍA | **jueves** | 23 | 15 | ×1.5 | 83 % |
| 62 - PIO BAROJA 20 | **miércoles** | 10 | 6 | ×1.5 | 83 % |
| 14 - BERMINGHAM | **jueves** | 13 | 9 | ×1.5 | 83 % |
| 17 - SAGASTIEDER | **lunes** | 11 | 7 | ×1.5 | 100 % |
| 40 - TOLOSA HIRIB.-IRAKASLE ESKOLA/MAGISTERIO | **viernes** | 18 | 12 | ×1.5 | 100 % |
| 37 - ANDOAIN | **viernes** | 9 | 7 | ×1.4 | 83 % |
| 41 - TOLOSA HIRIBIDEA-KARLOS SANTAMARIA | **viernes** | 15 | 10 | ×1.4 | 83 % |
| 10 - PEÑA Y GOÑI | **viernes** | 27 | 20 | ×1.3 | 100 % |
| 42 - BERIO 26 | **viernes** | 9 | 7 | ×1.3 | 83 % |
| 70 - TXAPILLO | **miércoles** | 7 | 5 | ×1.3 | 83 % |

Red entera (media de llegadas por estación y tarde): lunes 13.7, martes 13.1, miércoles 12.7, jueves 12.6, viernes 15.5

## Lectura (pendiente de validación nativa)

- El primer intento sin corregir lo dominaba el **viernes en todas partes**: la red
  entera sube +20 % las tardes de viernes (arranque del finde). Eso no es
  pintxo-pote; se deflacta y lo que queda es exceso *local*.
- **La señal más limpia es el jueves en Gros**: Gran Vía (×1.5) y Bermingham
  (×1.5), dos estaciones vecinas, mismo día, repetido >80 % de las semanas.
  Compatible con el juevintxo de Gros.
- **Miércoles**: Pio Baroja 20 y Txapillo. **Lunes**: Sagastieder (100 % de las
  semanas). Candidatos a pintxo-pote de barrio — o a otra cosa recurrente
  (deporte, clases): el dato no distingue el motivo, solo la recurrencia.
- El **viernes del corredor Antiguo/Ibaeta** (Magisterio, Karlos Santamaria,
  Berio, Andoain) sobrevive incluso tras deflactar: ahí el viernes por la tarde
  tiene algo propio además del efecto general.
- Método: llegadas 19-23 h de lunes a viernes, 30 tardes, exceso local >=1.3x
  repetido en >=70 % de las semanas. Con 6 ocurrencias por día de la semana, la
  consistencia pesa más que la magnitud.

## Indagación del entorno (2026-10-02): qué hay a 250 m de cada señal

Cruce de tres fuentes: OpenStreetMap (locales alrededor), guías web del
pintxo-pote, y la forma horaria del exceso en nuestros propios datos
(un bar llena a las 20 h y vacía a las 23; una clase llena y vacía con una
hora de diferencia).

| señal | entorno (OSM) | forma horaria | veredicto probable |
|---|---|---|---|
| **Gros, jueves** (Gran Vía + Bermingham) | 69 bares/cafés en 250 m | llega 20 h, se va 23 h | **pintxo-pote (juevintxo)** — día, zona, densidad y forma coinciden |
| **Pio Baroja, miércoles** | Pio Baroja Kiroldegia, gimnasio Metropolitan, 6 piscinas, cero bares | llega 20 h, se va 21 h | **deporte/clases del polideportivo**, no potes |
| **Sagastieder (Intxaurrondo), lunes** | Kultur Etxea, canchas (calistenia), colegio, 2 bares | llega 21 h, se va 22 h | **actividad con horario** (kultur etxea o deporte), no potes |
| **Txapillo (Aiete), miércoles** | colegios (Aiete, St. Patrick's) y campos | difusa | débil; probablemente actividad escolar/deportiva |
| **Benta Berri, viernes** (Magisterio, K. Santamaria, Berio) | 13 restaurantes + 7 bares/pubs (Campus, El Tercer Tiempo…), Escuela de Ingeniería, gimnasio | llega 18-21 h, se va 20-23 h | **tarde social fuerte propia** de la zona universitaria-hostelera; una guía de 2017 sitúa el pintxo-pote del Antiguo en *miércoles* — validar si cambió o si esto es otra cosa |

Lección de método: el detector encuentra **recurrencia**, no motivo. El mismo
patrón estadístico lo producen un pintxo-pote y una clase de spinning; los
separa el entorno (bares vs. polideportivo) y la duración de la estancia
(3 h vs. 1 h). Las dos cosas salen gratis: OSM y nuestros propios eventos.
