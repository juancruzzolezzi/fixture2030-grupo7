-- Hito 6 - Esquema (Grupo 7)
-- Crea el keyspace y las tres tablas del módulo. Se puede correr de nuevo sin
-- romper nada: todo usa IF NOT EXISTS (RNF7, idempotencia del esquema).
--
-- Orden obligatorio: primero el keyspace, después USE, recién ahí las tablas
-- (tal como marca la Clase 6).

CREATE KEYSPACE IF NOT EXISTS fixture2030
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

USE fixture2030;

-- Tabla principal: resuelve P1 (recientes) y P2 (ventana de 5 minutos).
-- La justificación completa de la clave está en docs/modelo_tabular.md y
-- docs/decisiones_de_particionamiento.md.
CREATE TABLE IF NOT EXISTS comentarios_por_bloque (
    partido_id      text,
    bloque_horario  text,
    creado_en       timestamp,
    comentario_id   uuid,
    usuario_id      text,
    usuario_nombre  text,
    contenido       text,
    estado          text,
    likes           int,
    reportes        int,
    PRIMARY KEY ((partido_id, bloque_horario), creado_en, comentario_id)
) WITH CLUSTERING ORDER BY (creado_en DESC, comentario_id ASC)
  AND comment = 'Tabla principal de comentarios, particionada por partido + bloque de 5 minutos (RF4, RF7)';

-- Estructura secundaria (RF10): historial de comentarios por usuario (P4).
CREATE TABLE IF NOT EXISTS comentarios_por_usuario (
    usuario_id      text,
    creado_en       timestamp,
    comentario_id   uuid,
    partido_id      text,
    contenido       text,
    PRIMARY KEY (usuario_id, creado_en, comentario_id)
) WITH CLUSTERING ORDER BY (creado_en DESC, comentario_id ASC)
  AND comment = 'Vista de acceso secundaria por usuario (RF10); duplicación controlada de comentarios_por_bloque';

-- Estructura secundaria: cola de moderación por partido (P3). Solo contiene
-- los comentarios marcados como pendientes u ocultos, no todo el volumen.
CREATE TABLE IF NOT EXISTS comentarios_pendientes_moderacion (
    partido_id      text,
    creado_en       timestamp,
    comentario_id   uuid,
    usuario_id      text,
    contenido       text,
    motivo          text,
    PRIMARY KEY (partido_id, creado_en, comentario_id)
) WITH CLUSTERING ORDER BY (creado_en DESC, comentario_id ASC)
  AND comment = 'Cola de moderacion; volumen chico, sin bucketing porque no lo necesita';

-- Verificación rápida de que las tres tablas quedaron creadas.
DESCRIBE TABLES;
