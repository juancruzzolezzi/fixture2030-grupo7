# Patrones de acceso — Hito 7 (Redis) — Fixture 2030

## Problema de concurrencia

Durante un partido popular del Fixture 2030, la plataforma recibe al mismo
tiempo:

- **Validación de sesión en cada request.** Todo usuario navegando genera una
  lectura de su sesión por cada acción. Es la operación más frecuente del
  sistema y la que menos puede tardar.
- **Lecturas repetidas del mismo dato.** Miles de personas abren la ficha del
  mismo partido en el mismo minuto. Sin caché, cada una de esas lecturas
  golpea la fuente de verdad para devolver exactamente la misma respuesta.
- **Actualizaciones simultáneas sobre la misma clave.** Un contador de visitas
  o una votación de "figura del partido" reciben incrementos concurrentes de
  usuarios distintos.

Los tres casos comparten algo: el dato es **transitorio o reconstruible**, se
localiza por una clave que la aplicación ya conoce, y necesita respuesta
inmediata. Ninguno de los tres es un dato de negocio que deba nacer en Redis.

## Supuestos declarados

| Supuesto | Valor asumido |
|---|---|
| Partidos | 12 (`F2030-001` … `F2030-012`, los mismos del Hito 5 y del Hito 6) |
| Formato de usuario | `user-00001` (el mismo del Hito 6) |
| Inactividad tolerada en una sesión | 30 minutos |
| Vida máxima de una copia de ficha de partido | 60 segundos |
| Concentración de tráfico | unos pocos partidos concentran la mayor parte de las lecturas |

## Patrones prioritarios

| ID | Quién y qué pide | Entrada | Respuesta | Frecuencia | Estructura | Vida |
|----|------------------|---------|-----------|------------|------------|------|
| **P1** | La API valida la sesión en cada request | `usuario_id` | Estado de la sesión | Muy alta (lectura) | Hash | TTL 1800 s |
| **P2** | La API registra actividad y renueva la sesión | `usuario_id` | Confirmación | Alta (escritura) | Hash + `EXPIRE` | Renueva TTL 1800 s |
| **P3** | Un usuario abre la ficha de un partido | `partido_id` | Ficha serializada | Muy alta (lectura) | String | TTL 60 s |
| **P4** | Cambia el marcador en la fuente de verdad | `partido_id` | — | Media (escritura) | `DEL` sobre la clave de P3 | Inmediato |
| **P5** | Se cuenta una visita a la ficha | `partido_id` | Total acumulado | Muy alta (escritura) | String entero | TTL 86400 s |
| **P6** | Un usuario vota la figura del partido / se pide el Top N | `partido_id` (+ jugador) | Ranking ordenado | Alta | Sorted Set | TTL 86400 s |
| **P7** | Se consulta quién está viendo la transmisión | `partido_id` | Conjunto de usuarios | Media | Set | TTL 3600 s |
| **P8** | Se muestran las últimas acciones del usuario | `usuario_id` | Lista reciente | Media | List | TTL 1800 s |

## Fuente de verdad vs. dato transitorio

| Dato | Dónde nace | Qué hace Redis |
|---|---|---|
| Equipos y jugadores | Módulo documental (Hito 4, MongoDB) | Nada: no se cachea en este módulo |
| Partidos, sedes, eventos | Módulo de grafos (Hito 5, Neo4j) | Guarda una **copia descartable** de la ficha (P3) |
| Comentarios | Módulo tabular (Hito 6, Cassandra) | Nada: no se cachea en este módulo |
| **Sesión de usuario** | **Redis** | Es el dueño del dato: es estado transitorio puro |
| **Contadores, votación, conectados, actividad** | **Redis** | Estado temporal de la jornada, no historia del torneo |

La distinción importa para saber qué pasa si Redis se cae: las fichas se
reconstruyen leyendo la fuente de verdad (más lento, pero correcto); las
sesiones se pierden y los usuarios vuelven a autenticarse. Ningún dato de
negocio del torneo desaparece, porque ninguno vive únicamente acá.

## Lo que este módulo deliberadamente no hace

- **No cachea equipos ni jugadores.** Cambian poco y no son el cuello de
  botella; agregar claves sin un patrón de lectura que las justifique
  contradice el criterio de diseño dirigido por acceso.
- **No guarda historial.** Los contadores y rankings son de la jornada y
  vencen. Un reporte histórico corresponde a otro módulo.
- **No busca por contenido.** Todo se localiza por clave conocida. Si hiciera
  falta buscar, sería señal de que el dato pertenece a otra tecnología.
