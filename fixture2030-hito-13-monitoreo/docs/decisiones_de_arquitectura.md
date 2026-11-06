# Decisiones de arquitectura

Base por base, con las diez preguntas de la consigna. **"Laboratorio"** es lo construido;
**"diseño"** es lo que proponemos para el torneo y no se probó.

En el laboratorio cada base es **un solo nodo** en una notebook. Todo lo que diga réplica, partición
entre nodos o región es diseño: ninguna de esas cosas está medida.

## Por qué no una sola estructura

Los datos del Fixture no se piden igual. Una ficha se lee por clave y cambia poco; un comentario se
escribe miles de veces y se lee por ventana de tiempo; un partido importa por lo que tiene conectado;
una sesión tiene que desaparecer sola; una estadística se pide por rango; y el estado de un partido no
puede saltearse pasos. Una única estructura haría barato uno de esos accesos y caros los otros.

Los módulos se relacionan por un **código compartido**: `F2030-xxx` para partidos y el código FIFA
para equipos, en todas las bases (unificado en el Hito 10). Cada ruta termina en un solo adaptador y
ninguna request combina dos bases. Así, si se cae una, las otras siguen: lo probamos en el Hito 11.

| Dato | Base | Consulta que la motivó | Consistencia que necesita | Si falla |
|---|---|---|---|---|
| Equipos y jugadores | MongoDB | Ficha por código, plantel filtrado | Fuerte al escribir, una lectura algo atrasada se tolera | No se ven fichas |
| Partidos y eventos | Neo4j | Partido con rivales y sede; evento con su jugador | Fuerte al escribir, una lectura algo atrasada se tolera | No se ven partido y eventos |
| Comentarios | Cassandra | Últimos comentarios de un partido en una ventana | Eventual | No se leen ni publican comentarios |
| Sesiones y caché | Redis | Lectura por clave en cada request | Baja: dato transitorio o reconstruible | Reautenticarse; caché reconstruible |
| Estadísticas | InfluxDB | Ventana temporal de un equipo | Eventual, unos segundos alcanzan | No se ve el panel en vivo |
| Estado del partido | IRIS | Avanzar la máquina de estados | **Fuerte**, transaccional | No se puede avanzar el estado |

## MongoDB: equipos y jugadores

1. **Tipo de dato**: fichas de 64 equipos y unos 1.600 jugadores. Atributos variables, poco volumen, cambian poco.
2. **Accesos**: ficha por código, equipos por confederación, plantel de un equipo por posición, siempre paginado.
3. **Modelo**: documental.
4. **Estructura**: colecciones `equipos` y `jugadores`, referenciadas por `equipo_id`, con validación `$jsonSchema` (`validationLevel: strict`) e índices `ix_equipo_posicion` e `ix_confederacion`.
5. **Carga y recuperación**: `generate_and_load.py`, con upsert por `_id` y semilla fija; `find_one` por `_id` y `find` con `limit`.
6. **Escala**: el volumen no justifica repartir datos. **Diseño**: réplicas para repartir lecturas (`secondaryPreferred`, Clase 13). **Laboratorio**: un nodo.
7. **Consistencia**: escribir en el primario. Leer una ficha algo atrasada no daña nada.
8. **Falla**: `/equipos` y `/jugadores` dan 503 a los ~3 s (pymongo intenta hasta el timeout); el resto sigue. Se pierde lectura, no datos.
9. **Trade-off**: al ser referencias y no un join, armar plantel más equipo requiere dos consultas. Además, la validación corre en cada escritura.
10. **Evidencia**: `GET /equipos/{codigo}` en 5-6 ms (`hito-10/docs/evidencia/latencia.txt`); `mongodb_*` en el panel.

## Neo4j: partidos y eventos conectados

1. **Tipo de dato**: partidos, equipos, sedes, jugadores y eventos, donde importa cómo se conectan.
2. **Accesos**: partido con sus dos rivales y sede; eventos de un partido con el jugador que los protagonizó.
3. **Modelo**: grafo.
4. **Estructura**: nodos `Partido`, `Equipo`, `Sede`, `Jugador`, `Evento`; relaciones `DISPUTA {condicion}`, `SE_JUEGA_EN`, `OCURRE_EN`, `PROTAGONIZA`, `PERTENECE_A`.
5. **Carga y recuperación**: `sembrar.cypher` con `MERGE` por clave de negocio; `MATCH` parametrizado, con recorrido de dos relaciones y `LIMIT`.
6. **Escala**: vertical (tabla de la Clase 13). Un torneo son 127 partidos, un grafo chico. **Diseño**: réplicas de lectura. **Laboratorio**: un nodo.
7. **Consistencia**: escribir eventos sin perderlos; se tolera una lectura algo atrasada.
8. **Falla**: las rutas de partido y eventos dan 503; los comentarios siguen.
9. **Trade-off**: difícil de repartir entre nodos y curva de aprendizaje de Cypher. Se acepta porque el grafo es chico.
10. **Evidencia**: `escenario_falla.sh neo4j` y `resultados_api.txt` del Hito 11. Sin métricas internas del motor.

**Consulta costosa con otra estructura**: el recorrido partido → evento → jugador. En una tabla o un documento serían uniones o lecturas encadenadas.

## Cassandra: comentarios

1. **Tipo de dato**: comentarios masivos, inmutables o casi, con picos en un gol. El Hito 6 proyectó hasta 300 comentarios/s por partido.
2. **Accesos**: últimos comentarios de un partido en un bloque; historial de un usuario.
3. **Modelo**: tabular de columnas anchas.
4. **Estructura**: `comentarios_por_bloque`, con `PRIMARY KEY ((partido_id, bloque_horario), creado_en, comentario_id)` y orden descendente; `comentarios_por_usuario`, duplicación controlada.
5. **Carga y recuperación**: `INSERT` en las dos tablas; `SELECT` con la partición completa y `LIMIT`. Nunca `ALLOW FILTERING`.
6. **Escala**: horizontal. La partición `(partido, bloque de 5 min)` evita que un partido se vuelva una partición infinita. **Diseño**: varios nodos y réplicas por región. **Laboratorio**: `SimpleStrategy` con `replication_factor: 1`, un nodo: **si se cae, no hay copia**.
7. **Consistencia**: eventual. Que un comentario aparezca un momento más tarde no daña nada.
8. **Falla**: 503 en leer y publicar. La API no guarda lo pendiente: lo que no se reintente desde el cliente se pierde.
9. **Trade-offs**: una tabla por consulta; dos `INSERT` sin transacción entre ellas; no se puede contar ni filtrar libremente (en el Hito 6 un conteo global dio timeout). **Hallazgo del Hito 12**: un reintento con la misma clave duplica la fila.
10. **Evidencia**: Hito 12: 807 comentarios aceptados, 807 en cada tabla, 0 faltantes; p95 de 26,7 ms al leer y 38,6 ms al publicar, a 60 ops/s en total.

**Bloque caliente**: un bloque del Hito 6 llegó a 32.141 filas y se proyectaron ~90.000. Leer los últimos 20 no debería depender del tamaño, porque lee desde la punta del orden. Eso sale del modelo, no lo medimos con 90.000 filas.

## Redis: sesiones y caché

1. **Tipo de dato**: estado transitorio (sesiones) y copias reconstruibles (ficha de partido).
2. **Accesos**: lectura por clave conocida en cada request.
3. **Modelo**: clave-valor en memoria.
4. **Estructura**: Hash `fixture2030:sesion:<id>` (TTL 1800 s) y String `fixture2030:cache:partido:<id>` (TTL 60 s).
5. **Carga y recuperación**: `HSET` + `EXPIRE`, `SET ... EX`, `HGETALL`, `GET`, `DEL`.
6. **Escala**: **diseño**: primero réplicas de lectura, después Cluster si el límite pasa a ser memoria o escritura (Hito 7). **Laboratorio**: un nodo con RDB y 256 MB.
7. **Consistencia**: baja a propósito. La caché se invalida con `DEL` al cambiar la fuente y el TTL de 60 s es el tope.
8. **Falla**: `/sesiones` da 503 en ~0,2 s en el Hito 11 y 504 en unos 4 s en el Hito 13, en otra notebook; `/equipos` sigue en 200. Se pueden perder las escrituras posteriores a la última foto RDB. Los votos no se pueden reconstruir.
9. **Trade-offs**: RAM cara. `volatile-lru` con TTL en todas las claves expone sesiones y votos a la expulsión; la devolución del Hito 7 propone separar instancias y **no está aplicado**.
10. **Evidencia**: `escenario_redis.txt` (Hito 11); `redis_*` en el panel; `prueba_de_falla.txt`.

**Límite honesto**: la API expone leer e invalidar la caché, pero las rutas de partido van a Neo4j sin pasar por Redis. El cache-aside completo está demostrado en los scripts del Hito 7, no en la API.

## InfluxDB: estadísticas en vivo

1. **Tipo de dato**: posesión, pases y tiros, una muestra por equipo y por segundo; audiencia por región; eventos.
2. **Accesos**: ventana temporal de un equipo en un partido; agregación por ventana.
3. **Modelo**: series temporales.
4. **Estructura**: tablas `estadisticas`, `audiencia`, `eventos`; tags `partido_id`, `equipo_id`, `sede`, `region`, `tipo_evento`, con valores acotados; menos de 2.800 series.
5. **Carga y recuperación**: line protocol en lotes de 10.000 líneas con reintentos; SQL con rango de tiempo y `LIMIT`.
6. **Escala**: la cantidad de series no crece con el volumen; retención de 50 días y resumen por ventanas. **Laboratorio**: un nodo, InfluxDB 3 Core.
7. **Consistencia**: una muestra puede tardar unos segundos. Los contadores acumulados se agregan con `MAX`, nunca `SUM`, y la API lo valida.
8. **Falla**: 503 caída, 504 congelada a los 3 s (Hito 11). La API no escribe estadísticas: si el productor no reintenta, se pierden las muestras de esa falla.
9. **Trade-offs**: granularidad contra almacenamiento; después de la retención ya no se puede ver un segundo puntual.
10. **Evidencia**: 706.151 puntos en 71 lotes, 9.945 puntos/s, 0 lotes fallidos (Hito 8). Proyección de 11,2 M de puntos: ~19 min, **estimada**.

## IRIS: entidad compleja y estado del partido

1. **Tipo de dato**: el partido como objeto, con árbitro y eventos, y reglas que no se pueden romper.
2. **Accesos**: detalle completo del partido; avanzar su estado.
3. **Modelo**: orientado a objetos.
4. **Estructura**: `Persona` y sus subclases (`Jugador`, `Arbitro`, `Tecnico`); `Partido` con máquina `Pendiente → EnJuego → Finalizado`; `Evento` hijo de `Partido`, inalterable.
5. **Carga y recuperación**: clases compiladas con `LoadDir`; Native SDK; proyección SQL disponible.
6. **Escala**: vertical (Clase 13). El volumen de partidos es chico. **Laboratorio**: un nodo.
7. **Consistencia**: **fuerte**. `%Save()` guarda padre e hijos juntos o nada.
8. **Falla**: 503. El cambio de estado no se aplica a medias. La API reconecta sola al volver IRIS (Hito 11). Las llamadas comparten una conexión y pasan de a una; si no consiguen turno en 3 s, 504. Nos pasó que el contenedor figurara `healthy` sin aceptar conexiones (`evidencia/hallazgo_iris_sin_super_server.md`).
9. **Trade-offs**: un producto más y un lenguaje más (ObjectScript); hay datos de partido también en Neo4j, unidos por código.
10. **Evidencia**: 26 verificaciones de la demo (Hito 9); una transición ilegal da 409 (`tests/integration`, Hito 10).

## Distribución y CAP

Con un nodo no hay partición de red que tolerar: **CAP no se puede demostrar en este laboratorio**.
Lo que sigue es la decisión de diseño para un torneo con sedes en dos continentes.

| Módulo | Si hay una partición de red, preferimos | Por qué | Qué pasaría si se cae una región (diseño) |
|---|---|---|---|
| Comentarios (Cassandra) | Disponibilidad | Mejor un comentario tarde que no poder comentar | La otra región sigue; se igualan después |
| Sesiones y caché (Redis) | Disponibilidad | Se reconstruyen o el usuario entra de nuevo | Reautenticación; la caché se rearma |
| Estadísticas (InfluxDB) | Disponibilidad | Mejor un panel con huecos que sin panel | Faltan muestras si el productor no reintenta |
| Fichas (MongoDB) | Consistencia al escribir, lecturas disponibles | Se escribe poco y antes del torneo | Se sigue leyendo desde una réplica; no se escribe hasta que haya primario |
| Grafo (Neo4j) | Consistencia al escribir, lecturas disponibles | Un evento mal conectado confunde | Igual que fichas |
| Estado del partido (IRIS) | **Consistencia** | Un partido no puede estar en dos estados | Prefiere rechazar el cambio antes que aceptarlo en dos lados |

**Ubicación de datos (diseño)**: comentarios y estadísticas cerca de la sede del partido y del público;
fichas y grafo replicados a todas las regiones, porque casi solo se leen; la escritura del estado
del partido en un único lugar.

## Mejora transversal (RF12)

### Medida: reutilizar el cliente, y cómo la vería ahora el panel

El Hito 12 midió que el adaptador de InfluxDB creaba un cliente HTTP por consulta. Al cambiarlo:
39,3 → 60 ops/s, p95 de estadísticas de 2.767 → 29 ms, CPU de la API de 556 % → 23 %. **Y mejoraron
los comentarios sin tocar Cassandra** (p95 de leer 34 → 27 ms, publicar 55 → 39 ms): por eso es
transversal. El costo de una base se trasladaba a las demás porque comparten el proceso de la API.

Conclusión: **un solo proceso de API es el punto que conecta a los seis módulos**. Separamos los
datos en seis bases, pero no el camino de acceso. Por eso el panel pone API y adaptadores lado a lado.
Se puede repetir con `INFLUX_REUSAR_CLIENTE=0` para mostrarlo (`defensa/demo.md`, opcional).

### Aplicada en este hito: la configuración defendida no era la que corría

Armando el panel de memoria de Redis, encontramos que el compose integrado arrancaba Redis sin
`maxmemory`, y `redis_memory_max_bytes` daba 0. El Hito 7 defendía 256 MB con `volatile-lru`, pero
eso quedaba en un script aparte. Lo agregamos al `docker-compose.yml` del Hito 10. Es un tipo de
error que solo aparece mirando el sistema corriendo.

### Observada: "healthy" no significa "se puede usar"

Con Docker marcando IRIS como `healthy`, sus 480 requests de la carga dieron 503. `database_up` lo mostró y las otras
cinco bases siguieron atendiendo. Se resolvió reiniciando IRIS; la causa de fondo no quedó comprobada
(`evidencia/hallazgo_iris_sin_super_server.md`). La mejora para todos los módulos es chequear el camino real de la API.

### Propuestas (no implementadas)

| Mejora | Por qué | Costo o riesgo | Cómo se validaría |
|---|---|---|---|
| Cache-aside real en `GET /partidos/{codigo}` | Es la ficha más leída y hoy siempre va a Neo4j | Invalidación; hay que respetar el `DEL` y el TTL de 60 s | p95 de la ruta y `redis_keyspace_hits_total`, misma carga |
| Tabla `comentarios_por_clave` para la idempotencia | Arregla el duplicado del Hito 12 | `IF NOT EXISTS` agrega idas y vueltas entre réplicas | p95 de publicar con la carga del Hito 12 |
| Separar Redis de sesiones y votos del de caché | Devolución del Hito 7 | Una instancia más | `redis_evicted_keys_total` |
| Healthcheck de IRIS contra el puerto 1972 | El de la imagen dio `healthy` con la API sin poder conectarse | Hay que probarlo sin que dé falsas alarmas al arrancar | Repetir el arranque y comparar con `database_up` |
| Más de una conexión a IRIS | Hoy las llamadas pasan de a una por una sola conexión | Límite de conexiones de la edición Community | p95 de la ruta de IRIS con más carga |
| Prueba por escalones | No conocemos el límite de la versión optimizada | Exigir la notebook | Subir usuarios de a poco y mirar el p95 |
| Quitar `ix_goles_desc` | Ninguna ruta lo usa y el recorte del Hito 4 sacó las estadísticas de jugadores | Casi nulo | Revisar la carga |

## Costo de mantener seis productos

Seis formas de hacer backup, de actualizar y de diagnosticar; seis clientes; seis lenguajes o dialectos
de consulta; más memoria (Cassandra sola usó ~4,6 GB en el Hito 12) y conocimiento repartido en el
equipo. La observabilidad tampoco es pareja: solo dos bases tienen vista interna.

Se justifica solo si cada base resuelve algo que las demás harían mal. El Hito 12 lo dice sin vueltas:
**si la carga real se pareciera a la de nuestro laboratorio, una base relacional alcanzaría para
comentarios y estadísticas**. La decisión se apoya en los picos proyectados y en el requisito de
seguir escribiendo ante una falla. Eso último todavía no está probado con varios nodos.
