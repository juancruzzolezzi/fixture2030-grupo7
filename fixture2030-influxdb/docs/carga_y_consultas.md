# Carga de datos, consultas y agregaciones

## 1. Carga de datos

| Etapa | Script | Qué hace |
|---|---|---|
| Generación | `scripts/generacion_puntos.sh` | Simula los partidos y escribe `data/puntos.lp` en line protocol + `data/manifiesto.env` con las cantidades esperadas |
| Carga | `scripts/carga_lotes.sh` | Divide el archivo en lotes y los escribe con `influxdb3 write --precision s` |
| Validación | `scripts/validacion.sh` | Compara lo cargado con el manifiesto |

**Generación**
- Origen: datos simulados con semilla fija por partido (`RANDOM=2030+k`), así cada ejecución genera los mismos valores.
- Calendario: 4 partidos por día desde el 13/06/2030 (13, 16, 19 y 22 h UTC), 105 minutos cada uno.
- Orden temporal: cada partido se genera en orden cronológico; los partidos se escriben uno detrás de otro.
- Volumen: configurable con `PARTIDOS`, `DURACION_SEG` e `INTERVALO_SEG`.
- Tipos: `posesion_pct` siempre con decimal (float); contadores y usuarios con sufijo `i` (integer).

**Carga**
- Tamaño de lote: 10.000 líneas (`LOTE`). Un lote de ese tamaño pesa ≈ 0,9 MB.
- Concurrencia: 1 (lotes secuenciales) en la prueba local.
- Precisión: segundos, declarada en cada escritura.
- Manejo de errores: cada lote se reintenta hasta 3 veces (`MAX_REINTENTOS`); si sigue fallando se registra en `data/lotes_fallidos.txt` y la carga continúa. Al terminar, `validacion.sh` muestra si faltan puntos.
- Medición: tiempo total y puntos/s, con versión de InfluxDB y recursos de Docker (`docs/evidencia/02_carga.txt`).

**Validación**
- Cantidad de puntos por tabla vs. manifiesto.
- Cantidad de series por tabla vs. lo esperado.
- Consistencia entre fuentes: el total de tiros según `estadisticas` (MAX por equipo) debe coincidir con la cantidad de eventos TIRO.
- Distribución de puntos por partido y tipos de columnas.

## 2. Consultas (`scripts/consultas_temporales.sh`)

| Consulta | Patrón | Qué demuestra |
|---|---|---|
| Ventana min 60–75 de ARG en M001 (+ conteo) | PA1 | Recuperación de una ventana temporal acotada |
| Último estado de cada equipo | PA2 | Pantalla en vivo: rango corto, alta frescura |
| Posesión en los últimos 5 min por equipo | PA3 | Comparación entre dimensiones (equipos) |
| Partidos en Buenos_Aires | PA4 | Filtro por la dimensión sede |
| Pico de usuarios por región | PA5 | Comparación entre fuentes/regiones |
| Goles de M001 | PA6 | Eventos individuales ordenados |

## 3. Agregaciones (`scripts/agregaciones.sh`)

| Consulta | Patrón | Función y justificación |
|---|---|---|
| AG1 Resumen por equipo | PA7 | AVG de posesión (muestra), MAX de pases y tiros (contadores). Se agrega SUM(tiros) a propósito para mostrar que sumar un contador acumulado da un valor sin sentido |
| AG2 Ventanas de 5 min | PA8 | Downsampling: la misma consulta de agregación acotada a cada rango de 5 minutos. 6.300 puntos → 21 filas |
| AG3 Eventos por tipo | PA6 | COUNT: cada punto es un evento |
| AG4 Partidos con más tiros | PA9 | COUNT de eventos TIRO, ordenado de mayor a menor (DESC, LIMIT 5) |
| AG5 Audiencia por partido | PA10 | MAX (pico), MIN y AVG de usuarios conectados; ordenado por pico de mayor a menor |

## 4. Interpretación de resultados

Resultados de la ejecución del 07/10/2026 (`docs/evidencia/04_consultas.txt`, `05_agregaciones.txt`, capturas `06_*` y `07_*`). El partido de referencia es M001, ARG vs POR en Buenos_Aires.

| Consulta | Resultado observado | Interpretación |
|---|---|---|
| PA1 ventana min 60–75 | 900 puntos (15 min × 60 s). Posesión de ARG entre 60,9 % y 70,0 %; tiros de 6 a 8 | La ventana recupera exactamente los puntos esperados. Al ser contador acumulado, los tiros del tramo se leen como diferencia: ARG hizo 2 tiros entre el minuto 60 y el 75 |
| PA2 pantalla en vivo | ARG 64,4 % / 753 pases / 11 tiros; POR 35,6 % / 383 pases / 14 tiros (14:44:59) | El último punto de cada serie es el estado actual del partido; basta leer el último minuto, no el partido entero |
| PA3 últimos 5 min | ARG 67,64 % y POR 32,36 % de posesión promedio | Los promedios suman 100 % porque las muestras de ambos equipos son complementarias en cada segundo |
| PA4 sede | M001 y M007 en Buenos_Aires, 6.300 puntos por equipo | El filtro por `sede` funciona sin que ese tag agregue series |
| PA5 audiencia por región | Mayor pico: OCEANIA (56.362); menor: AMERICA_CENTRAL (31.113) | El MAX muestra la capacidad que hay que soportar por región; el AVG muestra la carga sostenida |
| PA6 goles | ARG a los minutos 4 y 35 (2-0) | Los eventos individuales se recuperan con su instante exacto |
| AG1 resumen | MAX(tiros): ARG 11, POR 14. SUM(tiros): 35.278 y 49.508 | Sumar un contador acumulado da valores ≈ 3.200 a 3.500 veces mayores al real: confirma que la función correcta es MAX |
| AG2 ventanas de 5 min | 21 filas que resumen 6.300 puntos. Posesión de ARG: 51,6 % en los primeros 5 min, entre 62 % y 69 % el resto del partido, con una baja a ≈ 60 % entre los minutos 76 y 85. Pases de 30 a 753; tiros de 1 a 11 | El downsampling conserva la tendencia del partido con 300 veces menos filas |
| AG3 eventos por tipo | ARG: 11 tiros, 2 goles, 12 faltas, 7 córners. POR: 14 tiros, 16 faltas, 9 córners | Los 11 y 14 tiros coinciden con AG1: dos fuentes distintas dan el mismo resultado |
| AG4 tiros por partido | M006 (34), M008 (28), M003 (27), M004 (26), M001 (25) | Ranking del torneo calculado con COUNT de eventos |
| AG5 audiencia por partido | Mayor pico regional: M006 (67.799); menor: M003 (49.930) | M006 fue a la vez el partido con más tiros y con mayor pico de audiencia |

**Observación:** ARG ganó 2-0 con más posesión pero menos tiros que POR (11 contra 14). Los agregados describen lo que pasó y no explican por qué; como señala la clase, un promedio no explica causalidad.

**Límites de las consultas:** los datos son simulados; las conclusiones describen la agregación pedida y no explican causas. El promedio de posesión es un promedio de muestras de 1 segundo (equivale a ponderar por duración porque las muestras son equiespaciadas).
