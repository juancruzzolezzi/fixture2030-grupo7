# Integración con un Data Mart

## Pregunta analítica

**¿Los picos de comentarios de los hinchas coinciden con lo que pasa en la
cancha?** Para cada partido y cada ventana de 5 minutos: cuántos comentarios
hubo y de cuántos hinchas distintos, la posesión promedio de cada equipo,
cuántos tiros hizo cada uno y si hubo goles.

Le sirve a la organización y a la transmisión para entender qué momentos
generan actividad (y dimensionar la plataforma para el próximo partido). Es
una pregunta sobre partidos ya jugados o sobre la parte ya jugada: no necesita
el dato del segundo actual.

## Por qué no se responde con las fuentes operacionales

Hoy, para un partido, habría que:

- leer las 21 particiones de comentarios de Cassandra **enteras** para
  contarlas (en el Hito 6 un bloque caliente llegó a 32.141 filas, y el conteo
  global dio timeout);
- hacer 21 × 2 agregaciones en InfluxDB;
- consultar los eventos en Neo4j y los equipos en MongoDB;
- y unir todo en la API.

Para un solo partido son más de 40 consultas, y la pantalla del partido en
vivo, que es lo que medimos en este hito, compite con ellas por las mismas
bases. Si un dashboard hiciera eso en cada visita, cargaría las bases
operacionales con lecturas pesadas y repetidas, para un resultado que casi no
cambia. La proyección se calcula una vez por ventana y después se lee en una
sola consulta.

## Fuentes, atributos y medidas

| Fuente | Qué se toma | Para qué |
|---|---|---|
| Cassandra `comentarios_por_bloque` (Hito 6) | por `(partido_id, bloque_horario)`: `comentario_id`, `usuario_id`, `likes`, `estado` | comentarios, hinchas distintos, likes |
| InfluxDB `estadisticas` (Hito 8) | `posesion_pct` (muestra), `tiros` y `pases_completados` (contadores acumulados) por partido, equipo y tiempo | posesión promedio, tiros en la ventana |
| Neo4j `(:Evento)-[:OCURRE_EN]->(:Partido)` (Hito 5) | `tipo`, `minuto` | goles en la ventana |
| Neo4j `Partido`, `Sede`, `DISPUTA` | fecha, fase, sede, equipos y condición A/B | dimensión partido |
| MongoDB `equipos` (Hito 4) | nombre, confederación | dimensión equipo |

No se usan Redis (sesiones y caché, datos efímeros) ni IRIS (la entidad
compleja del partido no agrega nada a esta pregunta).

## Grano y estructura

**Una fila por partido y ventana de 5 minutos** (21 ventanas por partido de
105 minutos). Las medidas por equipo van en columnas A y B, según la condición
de `DISPUTA`.

```
hechos_actividad_ventana
  partido_id          F2030-006
  ventana             0..20   (minuto 0-5, 5-10, ...)
  ventana_inicio      2030-06-18T18:00:00Z
  comentarios         cantidad de comentario_id distintos, estado visible
  hinchas_distintos   cantidad de usuario_id distintos
  likes               suma
  posesion_a_avg      AVG(posesion_pct) del equipo A en la ventana
  posesion_b_avg
  tiros_a             MAX(tiros) en la ventana - MAX(tiros) hasta la ventana anterior
  tiros_b
  goles               eventos tipo 'Gol' con minuto dentro de la ventana
  puntos_a, puntos_b  cantidad de muestras de InfluxDB (control: 300 si la ventana está completa)
  completa            true si estaban las 4 fuentes y las 300 muestras por equipo
  actualizado_en, version_etl

dim_partido   partido_id, fecha, fase, sede, equipo_a, equipo_b      (Neo4j)
dim_equipo    equipo_id, nombre, confederacion                       (MongoDB)
```

Para todo el torneo son 127 × 21 ≈ 2.700 filas. Entra en cualquier base
relacional. Como el Fixture ya tiene IRIS, que habla SQL, la proyección podría
ser una tabla de IRIS, sin sumar otro producto. Una PostgreSQL también
serviría.

## Transformaciones y claves de unión

- **Partido**: `partido_id` con formato `F2030-xxx`, igual en las cinco
  fuentes. Esto funciona porque en el Hito 10 unificamos el código, que en
  IRIS era `M00x`.
- **Ventana**: cada fuente expresa el tiempo distinto, así que se normaliza
  todo a "número de ventana desde el inicio del partido":
  - Cassandra: `bloque_horario` ya es la ventana (AAAAMMDDHHmm truncado a 5 min).
  - InfluxDB: `date_bin(INTERVAL '5 minutes', time)` en UTC.
  - Neo4j: el evento tiene `minuto` y el partido solo tiene fecha, sin hora.
    La ventana es `minuto // 5`, y la hora de inicio se toma del primer punto
    de InfluxDB del partido: el sistema de datos empieza a emitir con el
    pitazo inicial.
- **Contadores**: `tiros` y `pases_completados` son acumulados (Hito 8). En la
  ventana se usa MAX y se resta el MAX de la ventana anterior. Nunca SUM.
- **Comentarios**: se cuentan por `comentario_id` distinto y solo con estado
  `visible`. Así no cuentan los moderados, y tampoco los duplicados por
  reintento que encontramos en este hito (ver `integridad_y_limitaciones.md`).

## Actualización, retraso y fallas

| | |
|---|---|
| Frecuencia | Durante el partido, cada 5 minutos, para la ventana que acaba de cerrar. Una pasada final 30 minutos después del partido. Una pasada nocturna que recalcula el día. |
| Retraso aceptable | La ventana se calcula 2 minutos después de cerrar, para dar margen a comentarios y muestras que llegan tarde. Retraso máximo de una fila: ~7 minutos durante el partido. Para esta pregunta alcanza. |
| Datos tardíos | Un comentario tardío cae en su bloque por `creado_en`. La pasada final y la nocturna lo incluyen. |
| Duplicados | Cada pasada recalcula la ventana completa y la reemplaza (upsert por `partido_id, ventana`). Correr el ETL dos veces da el mismo resultado. Los duplicados de origen se eliminan con COUNT DISTINCT. |
| Faltantes o falla parcial | Si una fuente no responde, la ventana se escribe con `completa = false` y esa medida en NULL (no en 0), y se reintenta en la próxima pasada. Una ventana sin muestras de InfluxDB tiene posesión NULL, no 50 %. |
| Procedencia | Cada fila guarda `actualizado_en` y `version_etl`. Cada columna sale de una sola fuente, según la tabla de arriba. |

## Validación de la proyección

- La suma de `comentarios` de las 21 ventanas tiene que coincidir con el
  conteo de `comentario_id` distintos visibles del partido en Cassandra.
- `puntos_a` y `puntos_b` tienen que ser 300 por ventana completa (1 por
  segundo). Si no, la ventana no está completa.
- La suma de `tiros_a` tiene que ser igual al `MAX(tiros)` del equipo A en
  todo el partido en InfluxDB, y lo mismo para B.
- La suma de `goles` tiene que coincidir con los eventos `Gol` del partido en
  Neo4j.

Son las mismas verificaciones de integridad que hicimos en la prueba de carga
(lo escrito contra lo guardado), aplicadas a la proyección contra sus fuentes.

## Fuente operacional vs proyección

| | Fuentes operacionales | Proyección |
|---|---|---|
| Consultas para un partido | 40+, en 4 bases | 1 consulta, 21 filas |
| Costo | Lee particiones completas de Cassandra | Lee 21 filas ya calculadas |
| Frescura | Al segundo | Hasta ~7 min de atraso durante el partido |
| Impacto en la pantalla en vivo | Compite por las mismas bases | Ninguno: el ETL corre cada 5 min, no por visita |
| Consistencia | Cada fuente en su momento | Una foto por ventana, con su `actualizado_en` |

La pantalla en vivo (el flujo de la prueba de carga) sigue yendo a las
fuentes operacionales, porque necesita el dato al segundo. La proyección es
solo para la pregunta analítica.

Esto es una propuesta de diseño: no construimos el ETL ni la tabla en este
hito, como permite la consigna.
