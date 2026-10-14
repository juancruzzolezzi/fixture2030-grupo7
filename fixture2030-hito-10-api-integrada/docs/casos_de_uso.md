# Casos de uso

Antes de escribir una ruta nos preguntamos qué necesidad del Fixture 2030
resuelve, no qué base la resuelve "de paso". Por eso hay seis grupos de
endpoints, uno por fuente, y ninguno genérico.

## 1. Consultar la ficha de un equipo o de un jugador (MongoDB)

- **Quién consume:** la pantalla de un equipo o de un jugador en la app.
- **Entrada:** código FIFA de 3 letras (equipo) o código equipo+dorsal (jugador); opcionalmente confederación o posición para filtrar/paginar el plantel.
- **Respuesta:** el documento tal cual lo diseñó el Hito 4, sin campos internos de más.
- **Si no existe:** 404, no una lista vacía disfrazada de éxito.
- **Si Mongo no responde:** 503.
- **Lectura**, sin efectos.

## 2. Ver un partido y sus eventos conectados (Neo4j)

- **Quién consume:** la pantalla de un partido, para mostrar rivales, sede y la línea de tiempo de eventos.
- **Entrada:** código de partido (`F2030-xxx`).
- **Respuesta:** el partido con sus dos equipos y la sede en una sola consulta; los eventos en otra, recorriendo partido→evento→jugador.
- **Si el partido no existe:** 404.
- **Lectura**, Cypher parametrizado, nunca texto libre del consumidor.

## 3. Leer y publicar comentarios de un partido (Cassandra)

- **Quién consume:** el feed de comentarios en vivo de un partido.
- **Entrada:** código de partido + bloque de 5 minutos (`bloque_horario`), igual que en el Hito 6: no existe "todos los comentarios del partido" sin ese dato, porque la tabla no está pensada para resolverlo así.
- **Respuesta:** la página de comentarios de ese bloque, ya ordenada por la clave de clustering.
- **Creación:** requiere una clave de idempotencia provista por el cliente (RF19): reintentar la misma request no duplica el comentario.
- **Si Cassandra no responde:** 503, nunca un 200 con una lista vacía.

## 4. Consultar el estado de una sesión o de la caché de un partido (Redis)

- **Quién consume:** el middleware de autenticación (sesión) y la pantalla de partido (caché de lectura).
- **Entrada:** `usuario_id` para la sesión, código de partido para la caché.
- **Respuesta de ausencia:** 404 tanto si la clave nunca existió como si ya expiró — Redis no distingue los dos casos, y la API no inventa una distinción que la fuente no puede sostener (RF6).
- **Invalidación de caché:** `DELETE`, idempotente (invalidar dos veces no es un error).
- **El token de sesión nunca sale en la respuesta**, aunque exista en el Hash.

## 5. Ver la evolución de una estadística en una ventana de tiempo (InfluxDB)

- **Quién consume:** el panel en vivo de un partido (posesión, tiros, pases).
- **Entrada:** partido, equipo, ventana `desde`/`hasta` (ISO 8601).
- **Respuesta:** los puntos crudos de la ventana, o una agregación (`/agregacion`) — pero solo con la función correcta para el campo: `AVG` para `posesion_pct` (una muestra), `MAX` para los contadores acumulados (`tiros`, `pases_completados`). Pedir `SUM` de un contador acumulado es un 400, no una cifra sin sentido (ver Hito 8).
- **Si `desde >= hasta`:** 400, antes de consultar InfluxDB.

## 6. Ver el objeto completo de un partido y avanzar su estado (IRIS)

- **Quién consume:** el panel operativo que controla el partido en vivo (árbitro, eventos, cambio Pendiente→EnJuego→Finalizado).
- **Entrada:** código de partido IRIS (los datos de prueba de este hito usan los códigos `M00x` que ya trae el Hito 9; ver nota de coherencia en `conectividad_y_configuracion.md`).
- **Respuesta de detalle:** el objeto completo con árbitro y eventos, navegado dentro de IRIS (no reconstruido con SQL desde afuera).
- **Cambio de estado:** pasa por `Partido.CambiarEstado()`, el mismo método del Hito 9. Pedir el mismo estado que ya tiene es un no-op exitoso (RF19); pedir una transición ilegal es 409, no un error genérico.
- **Si el partido no existe:** 404.
