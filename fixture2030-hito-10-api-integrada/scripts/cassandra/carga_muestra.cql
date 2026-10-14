-- Hito 6 - Carga de muestra (Grupo 7)
-- Conjunto chico y fijo para desarrollar y probar sentencias, tal como pide
-- la consigna en la Sección 5.3 ("una carga pequeña, suficiente para validar
-- las sentencias durante el desarrollo"). No es la carga masiva de RF11: esa
-- vive en carga_masiva.py.
--
-- Usa UUIDs literales (no uuid()) para que correr este script dos veces sea
-- idempotente (RNF7): la segunda vez sobreescribe las mismas filas con los
-- mismos valores, no inserta duplicados.

USE fixture2030;

-- Partido F2030-006 (ARG vs ESP, el de mayor audiencia de la muestra),
-- bloque 18:00-18:05 del 18/06/2030: varios comentarios normales.
INSERT INTO comentarios_por_bloque
  (partido_id, bloque_horario, creado_en, comentario_id, usuario_id, usuario_nombre, contenido, estado, likes, reportes)
VALUES
  ('F2030-006', '203006181800', '2030-06-18 18:00:12+0000', 10000000-0000-0000-0000-000000000001,
   'user-00001', 'hincha_arg_01', 'Vamos que arrancamos fuerte!', 'visible', 3, 0);

INSERT INTO comentarios_por_bloque
  (partido_id, bloque_horario, creado_en, comentario_id, usuario_id, usuario_nombre, contenido, estado, likes, reportes)
VALUES
  ('F2030-006', '203006181800', '2030-06-18 18:01:45+0000', 10000000-0000-0000-0000-000000000002,
   'user-00002', 'fanatico_esp', 'Buena presión de España en el inicio', 'visible', 1, 0);

INSERT INTO comentarios_por_bloque
  (partido_id, bloque_horario, creado_en, comentario_id, usuario_id, usuario_nombre, contenido, estado, likes, reportes)
VALUES
  ('F2030-006', '203006181800', '2030-06-18 18:03:30+0000', 10000000-0000-0000-0000-000000000003,
   'user-00001', 'hincha_arg_01', 'Casi el primero, que palo!', 'visible', 5, 0);

-- Mismo partido, bloque siguiente (18:05-18:10): acá ponemos el comentario
-- que después vamos a marcar como pendiente de moderación en crud.cql.
INSERT INTO comentarios_por_bloque
  (partido_id, bloque_horario, creado_en, comentario_id, usuario_id, usuario_nombre, contenido, estado, likes, reportes)
VALUES
  ('F2030-006', '203006181805', '2030-06-18 18:06:02+0000', 10000000-0000-0000-0000-000000000004,
   'user-00003', 'sospechoso_88', 'arbitro comprado esto es un escandalo', 'pendiente', 0, 4);

INSERT INTO comentarios_por_bloque
  (partido_id, bloque_horario, creado_en, comentario_id, usuario_id, usuario_nombre, contenido, estado, likes, reportes)
VALUES
  ('F2030-006', '203006181805', '2030-06-18 18:07:15+0000', 10000000-0000-0000-0000-000000000005,
   'user-00002', 'fanatico_esp', 'Bien cobrado el fuera de juego', 'visible', 2, 0);

-- Partido F2030-001 (ARG vs URU), bloque 20:00-20:05 del 13/06/2030: partido
-- distinto, para probar que las consultas por partido no se mezclan.
INSERT INTO comentarios_por_bloque
  (partido_id, bloque_horario, creado_en, comentario_id, usuario_id, usuario_nombre, contenido, estado, likes, reportes)
VALUES
  ('F2030-001', '203006132000', '2030-06-13 20:00:40+0000', 10000000-0000-0000-0000-000000000006,
   'user-00004', 'charrua_fiel', 'Arranca el clasico rioplatense', 'visible', 2, 0);

INSERT INTO comentarios_por_bloque
  (partido_id, bloque_horario, creado_en, comentario_id, usuario_id, usuario_nombre, contenido, estado, likes, reportes)
VALUES
  ('F2030-001', '203006132000', '2030-06-13 20:02:10+0000', 10000000-0000-0000-0000-000000000007,
   'user-00001', 'hincha_arg_01', 'Este partido siempre se juega raro', 'visible', 1, 0);

-- Vista por usuario: mismas filas, duplicadas a propósito (ver
-- docs/decisiones_de_particionamiento.md, "Duplicación controlada").
INSERT INTO comentarios_por_usuario (usuario_id, creado_en, comentario_id, partido_id, contenido)
VALUES ('user-00001', '2030-06-18 18:00:12+0000', 10000000-0000-0000-0000-000000000001, 'F2030-006', 'Vamos que arrancamos fuerte!');

INSERT INTO comentarios_por_usuario (usuario_id, creado_en, comentario_id, partido_id, contenido)
VALUES ('user-00002', '2030-06-18 18:01:45+0000', 10000000-0000-0000-0000-000000000002, 'F2030-006', 'Buena presión de España en el inicio');

INSERT INTO comentarios_por_usuario (usuario_id, creado_en, comentario_id, partido_id, contenido)
VALUES ('user-00001', '2030-06-18 18:03:30+0000', 10000000-0000-0000-0000-000000000003, 'F2030-006', 'Casi el primero, que palo!');

INSERT INTO comentarios_por_usuario (usuario_id, creado_en, comentario_id, partido_id, contenido)
VALUES ('user-00003', '2030-06-18 18:06:02+0000', 10000000-0000-0000-0000-000000000004, 'F2030-006', 'arbitro comprado esto es un escandalo');

INSERT INTO comentarios_por_usuario (usuario_id, creado_en, comentario_id, partido_id, contenido)
VALUES ('user-00002', '2030-06-18 18:07:15+0000', 10000000-0000-0000-0000-000000000005, 'F2030-006', 'Bien cobrado el fuera de juego');

INSERT INTO comentarios_por_usuario (usuario_id, creado_en, comentario_id, partido_id, contenido)
VALUES ('user-00004', '2030-06-13 20:00:40+0000', 10000000-0000-0000-0000-000000000006, 'F2030-001', 'Arranca el clasico rioplatense');

INSERT INTO comentarios_por_usuario (usuario_id, creado_en, comentario_id, partido_id, contenido)
VALUES ('user-00001', '2030-06-13 20:02:10+0000', 10000000-0000-0000-0000-000000000007, 'F2030-001', 'Este partido siempre se juega raro');

-- Cola de moderación: solo entra el comentario marcado como pendiente.
INSERT INTO comentarios_pendientes_moderacion (partido_id, creado_en, comentario_id, usuario_id, contenido, motivo)
VALUES ('F2030-006', '2030-06-18 18:06:02+0000', 10000000-0000-0000-0000-000000000004,
        'user-00003', 'arbitro comprado esto es un escandalo', 'palabra_filtrada:comprado');

-- Chequeo rápido de que entró todo.
SELECT partido_id, bloque_horario, count(*) AS comentarios
FROM comentarios_por_bloque
WHERE partido_id = 'F2030-006' AND bloque_horario = '203006181800';
