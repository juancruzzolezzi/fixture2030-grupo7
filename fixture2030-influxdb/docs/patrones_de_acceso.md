# Problema temporal y patrones de acceso

## 1. Problema temporal

Durante cada uno de los 127 partidos del Fixture 2030 la plataforma recibe observaciones que cambian segundo a segundo. No alcanza con conocer el estado actual (eso lo resuelve la caché del Hito 7): hay que poder reconstruir **cómo evolucionó** cada estadística dentro de un partido y comparar partidos del torneo.

| Fuente | Qué observa | Frecuencia | Quién la genera |
|---|---|---|---|
| Estadísticas de juego | Posesión, pases completados y tiros de cada equipo | 1 muestra por equipo por segundo | Sistema de datos del partido |
| Audiencia de la plataforma | Usuarios conectados por región | 1 muestra por región por segundo | Métricas operativas de la plataforma |
| Eventos de juego | Tiros, goles, faltas y córners, uno por punto | Cuando ocurren (decenas por partido) | Sistema de datos del partido |

**Volumen esperado** (partido de 105 minutos con tiempo adicionado = 6.300 s):

| Tabla | Cálculo | Puntos en el torneo |
|---|---|---|
| estadisticas | 127 partidos × 2 equipos × 6.300 s | 1.600.200 |
| audiencia | 127 partidos × 12 regiones × 6.300 s | 9.601.200 |
| eventos | ≈ 70 eventos por partido × 127 | ≈ 8.900 |
| **Total** | | **≈ 11.210.000 (10M+)** |

**Decisiones en tiempo real:** mostrar la pantalla del partido en vivo (último estado de cada equipo), detectar picos de audiencia por región para dimensionar la plataforma, y comparar equipos en ventanas cortas (por ejemplo, los últimos 5 minutos).

## 2. Patrones de acceso

Los patrones se definieron **antes** del modelo; cada tabla, tag y field del modelo se justifica con al menos uno de ellos (RNF4).

| ID | Pregunta | Quién consulta | Rango temporal | Dimensiones (filtro) | Medidas | Agregación | Respuesta esperada |
|---|---|---|---|---|---|---|---|
| PA1 | ¿Cómo evolucionó la posesión de un equipo entre el minuto 60 y el 75? | Analista / transmisión | 15 min dentro de un partido | partido_id, equipo_id | posesion_pct, pases, tiros | Ninguna (puntos ordenados por tiempo) | 900 puntos ordenados |
| PA2 | ¿Cuál es el último estado de cada equipo? (pantalla en vivo) | App del usuario | Último minuto | partido_id | posesion_pct, pases, tiros | Último punto por equipo | 1 fila por equipo |
| PA3 | ¿Cuál fue la posesión promedio de cada selección en los últimos 5 minutos? | Transmisión / app | 5 min | partido_id, agrupado por equipo_id | posesion_pct | AVG, MIN, MAX | 1 fila por equipo |
| PA4 | ¿Qué partidos se jugaron en una sede y con cuántos puntos registrados? | Organización | Todo el torneo | sede | conteo de puntos | COUNT, MIN/MAX(time) | 1 fila por partido y equipo |
| PA5 | ¿Cuál fue el pico de usuarios conectados por región? | Operación de la plataforma | Duración del partido | partido_id, agrupado por region | usuarios_conectados | MAX, MIN, AVG | 1 fila por región |
| PA6 | ¿Qué eventos (goles) ocurrieron y cuándo? | App / analista | Duración del partido | partido_id, tipo_evento | minuto, dorsal | Ninguna | Eventos ordenados por tiempo |
| PA7 | Resumen del partido por equipo | Analista | Duración del partido | partido_id | posesión, pases, tiros | AVG / MAX según semántica | 1 fila por equipo |
| PA8 | Tendencia del partido en ventanas de 5 min (dashboard) | Transmisión | Duración del partido | partido_id, equipo_id | posesión, pases, tiros | AVG / MAX por ventana | 21 ventanas |
| PA9 | ¿Qué partidos tuvieron más tiros? | Analista | Todo el torneo | tipo_evento, agrupado por partido_id | eventos | COUNT | Los 5 partidos con más tiros |
| PA10 | ¿En qué partido se dio el mayor pico de usuarios conectados? | Operación | Todo el torneo | agrupado por partido_id | usuarios_conectados | MAX, MIN, AVG | 1 fila por partido, de mayor a menor pico |
| PA11 | ¿Qué se conserva después del torneo? | Organización | Histórico | partido_id, equipo_id, region | Resúmenes por ventana | AVG / MAX / COUNT | Ver `retencion_y_granularidad.md` |

## 3. Precisión temporal

Las tres fuentes se escriben con **precisión de segundos** (`--precision s`, declarada en `scripts/config.sh` y en cada escritura). Las estadísticas y la audiencia se muestrean cada segundo, por lo que una precisión menor no aporta información a ninguna consulta de la tabla anterior. El timestamp lo asigna la **fuente** en el momento de la observación (no el momento de la carga).

## 4. Ausencia de puntos, retraso de la fuente y dato tardío

| Situación | Comportamiento del módulo |
|---|---|
| Ausencia de puntos | La consulta devuelve menos puntos o ninguna fila para ese rango. La validación compara la cantidad esperada (manifiesto) con la observada y marca la diferencia. |
| Retraso de la fuente | La pantalla en vivo (PA2) consulta el último minuto: si la fuente se atrasa, muestra el último punto disponible con su timestamp, para que se vea que el dato no es del instante actual. |
| Dato tardío | Se escribe con el timestamp original de la observación, por lo que queda ubicado en el lugar correcto de la serie aunque llegue después. |
