# Modelo multidimensional

Cada observación es **medida + dimensiones + tiempo**. En InfluxDB 3 Core se representa como un punto de line protocol con tabla, tags, fields y timestamp. Una **serie** es el conjunto de puntos que comparten tabla y combinación de tags.

## 1. Tabla `estadisticas`

**Fenómeno:** estado de juego de cada equipo, muestreado cada segundo.

```
estadisticas,partido_id=M001,equipo_id=ARG,sede=Buenos_Aires posesion_pct=52.3,pases_completados=128i,tiros=3i 1907587800
```

| Elemento | Nombre | Tipo | Semántica | Agregación correcta | Patrones |
|---|---|---|---|---|---|
| Tag | `partido_id` | texto (M001…M127) | Partido del torneo | Filtro | PA1, PA2, PA3, PA7, PA8 |
| Tag | `equipo_id` | texto (código de 3 letras) | Selección | Filtro / agrupación | PA1, PA3, PA7, PA8 |
| Tag | `sede` | texto | Sede del partido | Filtro | PA4 |
| Field | `posesion_pct` | float | **Muestra**: porcentaje de posesión en ese instante | AVG por ventana | PA1, PA3, PA7, PA8 |
| Field | `pases_completados` | integer (`i`) | **Contador acumulado** desde el inicio del partido | MAX (o diferencia entre inicio y fin de ventana). Nunca SUM | PA1, PA7, PA8 |
| Field | `tiros` | integer (`i`) | **Contador acumulado** desde el inicio del partido | MAX. Nunca SUM | PA1, PA7, PA8 |
| Timestamp | `time` | segundos | Instante de la muestra, asignado por la fuente | Rango / ventana | Todos |

**Serie:** `estadisticas + partido_id + equipo_id + sede` → una serie por equipo y por partido.

## 2. Tabla `audiencia`

**Fenómeno:** usuarios conectados a la plataforma por región mientras se juega un partido (métrica operativa).

```
audiencia,partido_id=M001,region=AMERICA_SUR usuarios_conectados=48210i 1907587800
```

| Elemento | Nombre | Tipo | Semántica | Agregación correcta | Patrones |
|---|---|---|---|---|---|
| Tag | `partido_id` | texto | Partido que se está viendo | Filtro / agrupación | PA5, PA10 |
| Tag | `region` | texto (12 valores) | Región geográfica de los usuarios | Filtro / agrupación | PA5 |
| Field | `usuarios_conectados` | integer (`i`) | **Estado medido** en ese instante | MAX (pico), MIN (caída), AVG (carga sostenida) | PA5, PA10 |
| Timestamp | `time` | segundos | Instante de la medición | Rango / ventana | Todos |

**Serie:** `audiencia + partido_id + region`.

## 3. Tabla `eventos`

**Fenómeno:** eventos individuales del juego. Cada punto representa **un** evento.

```
eventos,partido_id=M001,equipo_id=ARG,tipo_evento=GOL minuto=34i,dorsal=10i 1907588000
```

| Elemento | Nombre | Tipo | Semántica | Agregación correcta | Patrones |
|---|---|---|---|---|---|
| Tag | `partido_id` | texto | Partido | Filtro / agrupación | PA6, PA9 |
| Tag | `equipo_id` | texto | Equipo que generó el evento | Filtro / agrupación | PA6 |
| Tag | `tipo_evento` | texto (TIRO, GOL, FALTA, CORNER) | Tipo de evento | Filtro / agrupación | PA6, PA9 |
| Field | `minuto` | integer (`i`) | Minuto de juego, para mostrar | Ninguna | PA6 |
| Field | `dorsal` | integer (`i`) | Dorsal del jugador involucrado | Ninguna | PA6 |
| Timestamp | `time` | segundos | Instante del evento | Rango / ventana | Todos |

**Agregación:** COUNT por ventana o por partido (un punto = un evento).

## 4. Resumen de las tres medidas de naturaleza diferente (RF5)

| Medida | Naturaleza | Función | Qué pasa si se usa otra |
|---|---|---|---|
| `posesion_pct` | Muestra | AVG | La suma de porcentajes no tiene significado |
| `tiros`, `pases_completados` | Contador acumulado | MAX | SUM suma cada lectura del contador: multiplica el valor real por la cantidad de muestras (AG1 lo demuestra) |
| `usuarios_conectados` | Estado medido | MAX / MIN / AVG | El promedio oculta el pico que define la capacidad necesaria |
| Puntos de `eventos` | Evento individual | COUNT | MAX o AVG de un evento no responden cuántos ocurrieron |

## 5. Tipos y consistencia de esquema

InfluxDB 3 Core define el esquema al escribir. Por eso el generador escribe **siempre** `posesion_pct` con decimal (float) y los contadores con sufijo `i` (integer). Mezclar tipos para el mismo field produciría un conflicto de esquema. La validación (`scripts/validacion.sh`, consulta 5) muestra los tipos registrados.

## 6. Coherencia con el TPO

| Módulo | Tecnología | Relación con este hito |
|---|---|---|
| Hito 4 — equipos y jugadores | MongoDB | `equipo_id` usa el código de la selección; la ficha del equipo y del jugador (dorsal) vive en MongoDB, aquí solo se guarda el código y el dorsal como valor. |
| Hito 5 — partidos y eventos | Neo4j | `partido_id` identifica el mismo partido del grafo. Neo4j responde **qué** se relaciona (jugador–gol–partido); InfluxDB responde **cuándo** y **cuántos** por ventana. |
| Hito 6 — comentarios | Cassandra | Los comentarios masivos se quedan en Cassandra; aquí solo se registran métricas numéricas. |
| Hito 7 — usuarios y sesiones | Redis | Redis guarda la sesión de cada usuario; aquí solo se guarda el **total** de usuarios conectados por región, sin identificadores individuales. |

> Si los hitos anteriores del grupo usan otro formato de identificadores de partido o códigos de equipo, ajustar las listas `EQUIPOS` y `SEDES` y el formato `M%03d` en `scripts/generacion_puntos.sh`.
