# Defensa final ante la FIFA

## La pregunta central

**¿Por qué esta combinación de modelos, estructuras, estrategias de distribución y mecanismos de
observabilidad resulta adecuada para el Fixture Mundial 2030 bajo las condiciones planteadas?**

Porque los datos del Fixture tienen patrones de acceso incompatibles entre sí, y cada modelo hace
barato el acceso que su dato necesita: la clave en Redis, la partición por partido y bloque en
Cassandra, el recorrido en Neo4j, la ventana temporal en InfluxDB, el documento en MongoDB y la regla
transaccional en IRIS. Separarlos limita el daño de una falla: lo probamos cayendo bases y viendo que
el resto seguía. Y el monitoreo permite saber dónde está el problema antes de culpar a una base: la
mejora más grande que medimos no estuvo en ninguna base, estuvo en cómo la API usaba un cliente.

**Lo que no afirmamos**: que escale al tráfico de un Mundial. Medimos 60 ops/s con 30 usuarios en una
notebook y un nodo por base. La distribución entre nodos y regiones es diseño, no evidencia. Y si la
carga real fuera como la de nuestro laboratorio, una base relacional alcanzaría para parte de esto.

## Qué mostrar para cada idea

| Idea | Cómo se demuestra |
|---|---|
| Cada base tiene un patrón distinto | Comentarios por partición contra recorrido de grafo (`defensa/demo.md`) |
| Una falla no tira todo | Prueba de falla en Grafana y en `prueba_de_falla.txt` |
| Se distingue API de base | Panel "API contra adaptadores" y el caso del Hito 12 |
| Las escrituras no se pierden con carga | `integridad_optimizada.txt` |
| Conocemos los límites | `docs/limitaciones_y_evidencia.md` |

## Preguntas de la FIFA

Son ideas para responder con palabras propias, no un texto para memorizar. Cualquiera del grupo puede
recibir cualquiera.

**¿Por qué eligieron este modelo para este tipo de dato?**
Partimos del acceso, no de la tecnología. Tabla en `decisiones_de_arquitectura.md`. Ejemplo:
comentarios en Cassandra porque se escriben masivamente, se leen por partido y ventana, y toleran llegar un poco tarde.

**¿Qué consulta sería costosa con otra estructura?**
Eventos de un partido con su jugador: en Neo4j, un recorrido; en documentos o tablas, uniones o lecturas
encadenadas. Al revés también: contar todos los comentarios del torneo es caro en Cassandra (dio
timeout en el Hito 6) y trivial en una relacional. Por eso se propone un Data Mart (Hito 12).

**¿Cómo se distribuyen los datos?**
Laboratorio: un nodo por base. Hay que decirlo primero. Diseño: Cassandra reparte por `(partido_id,
bloque_horario)`, con réplicas por región; MongoDB y Neo4j replican para lectura; Redis, primero
réplicas y luego Cluster. Ninguna se probó.

**¿Qué sucede si se cae un nodo o una región?**
Medido: se cae la base entera y solo se afectan sus rutas (503/504), el resto sigue, y al volver se
recupera sin reiniciar la API. No medido: nodo dentro de un clúster o región. En el laboratorio, con
`replication_factor: 1`, un nodo de Cassandra caído deja sin comentarios. Diseño: tabla de CAP.

**¿Qué garantía de consistencia necesita este módulo?**
Fuerte: el estado del partido en IRIS. Eventual: comentarios y estadísticas. Baja: caché y sesión.

**¿Qué parte de la respuesta puede ser eventual?**
Que un comentario tarde en aparecer; una estadística de unos segundos atrás; la ficha en caché hasta 60 s,
aunque el `DEL` la invalida antes. **No** puede ser eventual el estado del partido.

**¿Dónde se encuentra el cuello de botella?**
El último que medimos era la creación de clientes en la API (Hito 12), y se corrigió. El siguiente no
lo conocemos: la versión optimizada no se llevó a su límite. Candidatos, sin medir: el único proceso de
uvicorn y el bloque caliente de Cassandra.

**¿Cómo distinguen que el problema está en la API y no en la base?**
Comparamos el p95 de la API con el de los adaptadores y con el motor. En el Hito 12: API al 556 % de
CPU, InfluxDB al 9 %, una sola ruta lenta. Ojo con el adaptador: incluye el cliente.

**¿Qué métrica observarían primero ante un aumento de latencia?**
1. ¿Es una ruta o todas? `api_latency_seconds` por ruta. 2. ¿API o adaptador? Panel de comparación.
3. ¿Hay errores? `database_errors_total`. 4. ¿Saturación? CPU y memoria.

**¿Qué evidencia tienen de que la optimización funcionó?**
Mismo commit, misma carga y misma máquina, cambiando una sola variable:
39,3 → 60 ops/s y 2.767 → 29 ms en estadísticas. La hipótesis se probó antes de tocar el código, y
`comparar.py` verifica las condiciones.

**¿Qué cambiarían si el tráfico se multiplica?**
Primero medir por escalones para saber qué se rompe. Después, lo que indique la evidencia: varios procesos
de API, nodos de Cassandra, réplicas de lectura, cache-aside. Lo que no haríamos es escalar todo "por las dudas".

**¿Qué se perdería o retrasaría durante una falla?**
Cassandra: comentarios que el cliente no reintente, porque la API no los guarda. Redis: sesiones activas si
se pierde la memoria y lo posterior a la última foto RDB, y los votos, que no se reconstruyen. InfluxDB:
muestras si el productor no reintenta. IRIS: el cambio de estado se rechaza, no queda a medias. MongoDB y
Neo4j: en la API solo se leen, se retrasa la lectura.

**¿Qué información no pueden afirmar porque no fue medida?**
Capacidad máxima, 300 comentarios/s, varios nodos, regiones, varios partidos simultáneos, red real y
comparación medida contra relacional. Lista completa en `limitaciones_y_evidencia.md`.

**¿Qué costo operativo agrega mantener seis modelos o productos?**
Seis backups, actualizaciones, clientes y diagnósticos, más memoria y más conocimiento. Se acepta solo si
cada uno resuelve algo que los otros harían mal. Si hubiera que recortar, habría que evaluar primero lo
que más se superpone: partido en Neo4j y en IRIS.

**¿Por qué no usaron SQL?**
No es que SQL no pueda. En el flujo medido, Postgres haría gratis la idempotencia y las consultas no
previstas. Lo que cuesta es escalar escrituras más allá de un primario y seguir escribiendo ante una
falla. Conviene NoSQL con los picos proyectados; conviene relacional con una carga como la del laboratorio. No lo medimos.

**¿Cómo escala Cassandra en un pico de gol?**
Todos escriben en el bloque actual de ese partido: la partición limita el tamaño, pero es un punto
caliente. Con varios nodos, otros partidos no se verían afectados y ese bloque tendría sus réplicas. Medimos
10,9 escrituras/s sin errores y no hicimos el pico. El panel "Escrituras por partido" es donde se vería.

**¿Cómo se evita que una consulta de alto volumen bloquee todo?**
Partición obligatoria y `LIMIT`, rangos acotados, timeouts de 2-3 s, 504 en lugar de quedar colgados, y bases
separadas. **No queda resuelto del todo**: todos comparten el proceso de la API, y el Hito 12 mostró que el
costo de una ruta afecta a las otras.

**¿Qué decisión tomarían si una base queda temporalmente indisponible?**
Seguir en servicio degradado: no se saca la API de servicio por una sola base, ni se devuelve un 200 vacío.
Se recupera esa base con `start`, sin borrar volúmenes, y se confirma en el panel. Las alertas dicen por dónde empezar.

**¿Qué datos son operacionales y cuáles podrían proyectarse a una vista analítica?**
Operacionales: todos los módulos actuales. Proyección propuesta (Hito 12, no construida): actividad por ventana
de 5 minutos, para saber si los picos de comentarios coinciden con lo que pasa en la cancha.

## Mejoras para una siguiente iteración

Tabla de `decisiones_de_arquitectura.md`, sección "Propuestas", más exporters de Cassandra y Neo4j
y notificación real de alertas.
