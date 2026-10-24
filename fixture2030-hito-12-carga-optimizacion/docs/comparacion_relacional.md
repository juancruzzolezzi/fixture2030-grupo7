# Comparación con una alternativa relacional

Esta comparación es **conceptual**: no armamos ni medimos una base
relacional. Lo único medido en este hito es la API actual (ver
`evidencia/`). Analizamos solo el flujo de la prueba: leer comentarios,
publicar un comentario y leer la ventana de estadísticas de un partido en
vivo.

## Cómo sería el flujo en una base relacional (por ejemplo PostgreSQL)

**Unidad de información**: una fila por comentario y una fila por muestra de
estadística, igual que hoy. Lo que cambia es cómo se organizan.

```sql
comentario (
  comentario_id      uuid PRIMARY KEY,
  partido_id         text REFERENCES partido,
  usuario_id         text REFERENCES usuario,
  creado_en          timestamptz NOT NULL,
  contenido          varchar(280),
  estado             text,
  likes              int,
  clave_idempotencia text UNIQUE            -- resuelve el reintento duplicado
)
INDEX (partido_id, creado_en DESC)          -- leer comentarios de un bloque
INDEX (usuario_id, creado_en DESC)          -- reemplaza la tabla comentarios_por_usuario

estadistica (
  partido_id text, equipo_id text, ts timestamptz,
  posesion_pct numeric, pases_completados int, tiros int,
  PRIMARY KEY (partido_id, equipo_id, ts)
)  -- particionada por rango de fecha, para borrar lo viejo (retención del Hito 8)
```

**Operaciones**

| Operación del flujo | Relacional | Hoy (NoSQL) |
|---|---|---|
| leer_comentarios | `WHERE partido_id = ? AND creado_en >= ? AND creado_en < ? ORDER BY creado_en DESC LIMIT 20`: recorre un rango del índice | Lee la punta de una partición `(partido, bloque)` |
| publicar_comentario | Un `INSERT ... ON CONFLICT (clave_idempotencia) DO NOTHING` en una transacción: actualiza la tabla y los dos índices juntos | Dos `INSERT` en dos tablas, sin transacción entre ellas |
| leer_estadisticas | Rango sobre la clave primaria `(partido, equipo, ts)` | Consulta SQL a InfluxDB con filtro de tags y tiempo |

**Garantías**: ACID. El comentario y sus índices se escriben juntos o no se
escriben. La restricción `UNIQUE` hace que un reintento no duplique: es justo
el hallazgo de integridad de este hito, y en relacional sale casi gratis. En
Cassandra hay que armar una tabla extra y pagar una transacción liviana.

## Qué sería más simple y qué más complejo

| Más simple en relacional | Más complejo en relacional |
|---|---|
| Idempotencia y unicidad con una restricción | Escalar escrituras más allá de un nodo: hace falta particionar o shardear a mano (o una extensión como Citus) |
| Una sola tabla de comentarios y un índice en vez de dos tablas que mantener sincronizadas | Todos los comentarios de un partido caliente se insertan al final del mismo índice (`partido_id, creado_en`): contención en las últimas páginas del índice |
| Consultas no previstas (por ejemplo, contar comentarios por ventana con `GROUP BY`) | Réplicas de lectura con atraso, y la conmutación por falla del primario |
| Estadísticas: 1,6 M de filas por torneo (Hito 8) es poco para una relacional | Funciones de series temporales (`date_bin`, retención por tiempo) necesitan extensiones o trabajo manual |

## Cómo crecería

- **Volumen**: los comentarios de un torneo (Hito 6: 160.000 solo en
  F2030-006) y las estadísticas (1,6 M) entran sin problema en un nodo
  relacional bien indexado.
- **Concurrencia de escritura**: el Hito 6 planteó picos de 300 comentarios/s
  en un partido, con varios partidos el mismo día. Un nodo relacional puede
  aguantar algunos miles de inserts por segundo, pero siempre en un único
  primario. Cassandra reparte la escritura por `(partido, bloque)` entre
  nodos y sigue aceptando escrituras si se cae uno.
- **Concurrencia de lectura**: en relacional se escala con réplicas, que leen
  con algo de atraso. Para comentarios en vivo eso es aceptable.

## En qué condición conviene cada una

- **Conviene NoSQL (como está)** si el volumen de escritura en picos es el
  del Hito 6 o mayor, con varios partidos simultáneos, y se necesita seguir
  escribiendo aunque se caiga un nodo. Los patrones de acceso son pocos,
  conocidos y por partido, que es lo que modela bien la partición de
  Cassandra.
- **Conviene relacional** si la carga real es parecida a la de nuestro
  laboratorio (decenas de escrituras por segundo y un partido a la vez), si la
  unicidad y las transacciones pesan más que la escala, o si van a aparecer
  muchas consultas no previstas, como las del Data Mart.

## Qué nos enseñó la prueba sobre esta comparación

El cuello de botella que medimos no estaba en ninguna base. Estaba en cómo la
API usaba el cliente HTTP de InfluxDB. Cambiar Cassandra o InfluxDB por una
relacional no lo habría resuelto: una API que abre una conexión nueva por
consulta tiene el mismo problema con cualquier base. Antes de elegir
tecnología por rendimiento, hay que medir dónde está el tiempo.

## Qué no pudimos medir

- No corrimos el mismo escenario contra PostgreSQL. Cualquier número de
  rendimiento relacional de arriba es una referencia general, no una medición
  nuestra.
- No probamos varios nodos ni de Cassandra ni de una relacional: todo corre en
  una sola notebook.
- No medimos contención con varios partidos a la vez.
