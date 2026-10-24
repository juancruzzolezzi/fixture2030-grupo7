# Flujo y escenario de carga

## Flujo elegido: la pantalla del partido en vivo

Elegimos lo que hace la app de un hincha mientras mira un partido. Es el
momento de más tráfico del Fixture y combina lecturas y escrituras sobre dos
módulos distintos de la cursada, a través de la API del Hito 10.

| | |
|---|---|
| Quién genera la operación | La app del hincha (usuario virtual del generador) |
| Partido | `F2030-006`, ARG vs ESP, el de más audiencia en los Hitos 6 y 8. La prueba simula el minuto 60. |
| Fuentes | Cassandra (comentarios, Hito 6) e InfluxDB (estadísticas, Hito 8) |
| Endpoints | Los mismos de la API del Hito 10, sin cambios en el contrato |
| Volumen proyectado | Hito 6: picos de hasta 300 comentarios/s en un partido de audiencia alta. Hito 8: 1 muestra por equipo por segundo. |

Las tres operaciones del flujo:

| Operación | Endpoint | Tipo | Fuente | Correcta si... |
|---|---|---|---|---|
| leer_comentarios | `GET /partidos/F2030-006/comentarios?bloque_horario=…&limite=20` | lectura | Cassandra, una partición `(partido, bloque)` | 200 y vuelven exactamente 20 comentarios |
| publicar_comentario | `POST /partidos/F2030-006/comentarios?bloque_horario=203006181900` | escritura | Cassandra, `comentarios_por_bloque` + `comentarios_por_usuario` | 201 y viene el `comentario_id`. Después se verifica en la base (ver integridad). |
| leer_estadisticas | `GET /partidos/F2030-006/estadisticas?equipo_id=…&desde=18:55&hasta=19:00&limite=300` | lectura de ventana temporal | InfluxDB | 200 y vuelven 300 puntos (uno por segundo), ordenados |

No se llama a las seis bases en cada request: la pantalla en vivo necesita
comentarios y estadísticas, nada más. Equipos, sede y fase del partido (Mongo y
Neo4j) cambian poco y la app los puede tener guardados.

Lo que se registra como error: cualquier status distinto del esperado
(`http_503`, `http_504`, ...), `timeout` (más de 10 s), `conexion` (la API no
atiende) y `contenido_invalido` (status correcto pero cantidad o forma
incorrecta). No damos por buena una respuesta solo porque devolvió 200.

## Escenario

Todos los valores salen de `config/configuracion-ejemplo.env`. Si se cambian,
se guardan en el resultado de cada corrida.

| Parámetro | Valor | Por qué |
|---|---|---|
| Datos iniciales | 6.300 comentarios (21 bloques × 300) y 12.600 puntos (105 min × 2 equipos × 1/s) | Un partido completo, ver `datos-o-generadores/README.md` |
| Usuarios virtuales | 30 | Lo que una notebook genera y atiende sin trabarse (RNF9) |
| Tasa objetivo | 2 operaciones/s por usuario = **60 ops/s** | Cada usuario espera su respuesta antes de la siguiente (modelo cerrado). Si la API tarda más de 0,5 s, la tasa real baja y se cuenta como "operación atrasada". |
| Proporción | 60 % leer comentarios, 20 % publicar, 20 % leer estadísticas | 80 % lecturas / 20 % escrituras. Mucha más gente lee que escribe. |
| Distribución de claves | 80 % de las lecturas de comentarios van al bloque actual (19:00), 20 % a un bloque anterior al azar. Todas las escrituras van al bloque actual. Estadísticas: ARG o ESP al 50 %. | El bloque actual es la clave "caliente", como en un partido real. |
| Calentamiento | 10 s con 5 usuarios | Conexiones abiertas y cachés de la JVM calientes. No se compara. |
| Rampa | 20 s, de 5 a 30 usuarios | Subida gradual. No se compara. |
| Sostenimiento | 60 s con 30 usuarios | **Es lo que se compara.** |
| Corte seguro | Se detiene si en 5 s falla más del 20 % de las operaciones, o con Ctrl+C | Guarda lo medido hasta ahí y marca la corrida como no completa. |
| Ante timeout o error | Se registra y el usuario sigue con la próxima operación. Una escritura sin respuesta queda como "resultado desconocido" y se resuelve en la validación. | |
| Limpieza | Los datos van a un keyspace (`fixture2030_h12`) y una base de InfluxDB (`fixture2030_h12`) propios. `limpiar_datos_de_prueba.py --confirmar` los borra. Los datos del Hito 10 no se tocan. | RNF7 y RNF11 |

Cada usuario virtual tiene su propia semilla (`vu-0`, `vu-1`, ...): la línea
base y la corrida optimizada hacen la misma secuencia de operaciones.

La API de la prueba la levanta el propio script en el puerto 8010, con un
solo proceso y sin `--reload`, apuntando al keyspace y a la base de la prueba.
Así no se mezcla con la API del puerto 8000 que se usa en los Hitos 10 y 11.

## Qué se mide y cómo

| Medida | Cómo | Unidad |
|---|---|---|
| Latencia | `time.perf_counter()` en el generador, antes de mandar y al recibir la respuesta completa. Incluye red local, API y base. | ms; min, p50, p90, p95, p99, máx y promedio. Solo respuestas correctas. |
| Throughput | Respuestas correctas / duración de la fase | ops/s |
| Errores | Cantidad por tipo (ver arriba) | cantidad |
| CPU y memoria de la API | `psutil` sobre el proceso de uvicorn, cada 5 s | % de un núcleo, MB |
| CPU del generador | `psutil` sobre el propio proceso | % de un núcleo. Si se acerca al 100 %, el límite podría ser el generador y no la API. |
| CPU y memoria de las bases | `docker stats --no-stream` de `h10-cassandra` y `h10-influxdb`, cada 5 s | % y MB |
| Estabilidad | p95 y ops/s cada 5 s | tabla "Evolución" del resultado |

Así quedan separados el generador, la API, cada base y la notebook. Ninguna
cifra se presenta sin su corrida, su commit y su entorno: todo eso está en el
encabezado de cada archivo de `evidencia/`.
