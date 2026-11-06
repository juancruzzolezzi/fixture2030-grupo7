# Guion de la defensa (máximo 20 minutos)

Hay que ensayarlo con cronómetro. Cada uno habla unos 5 minutos, pero todos tienen que poder
responder sobre cualquier módulo. Dejar 20 s de margen en cada cambio de orador.

| Tiempo | Bloque | Quién | Qué decir | Con qué |
|---|---|---|---|---|
| 0:00-2:00 | **Inicio** | Bernardo | El problema de la FIFA: 127 partidos, seis tipos de dato con accesos incompatibles. La decisión: un modelo por patrón de acceso, unidos por código. Y el aviso: mostramos lo medido y separamos lo que es diseño. | Diapositivas 1-2 |
| 2:00-5:00 | **Arquitectura** | Bernardo | Recorrido: qué guarda cada base y por qué no una sola. Cada ruta termina en un adaptador. | Diapositivas 3-4 |
| 5:00-11:00 | **Decisiones** | Sebastián (Cassandra e IRIS) y Mailén (Redis, distribución y CAP) | Tres casos a fondo: partición de Cassandra, consistencia fuerte en IRIS, TTL e invalidación en Redis. Después distribución y CAP: qué es laboratorio y qué es diseño. | Diapositivas 5-8 |
| 11:00-14:00 | **Operación** | Sebastián | Dos flujos: comentarios (partición) contra eventos (recorrido). Decir qué base responde y por qué el patrón es distinto. | Diapositiva 9 y `defensa/demo.md`, flujos 1 y 2 |
| 14:00-18:00 | **Evidencia** | Juan Cruz | Leer el panel: qué significa cada fila. Mostrar la falla de Redis, antes preparada: qué se cayó y qué siguió. Contar el hallazgo del Hito 12 con números y el caso de IRIS "healthy" que `database_up` marcó caída. | Grafana y diapositivas 10-12 |
| 18:00-20:00 | **Cierre** | Mailén | Por qué es adecuada, qué trade-offs aceptamos, qué no medimos y qué haríamos después. Responder la pregunta central. | Diapositivas 13-14 |

## Qué decir en cada diapositiva

Las diapositivas acompañan: tienen poco texto a propósito. Esto es lo que se dice, con palabras propias.

| # | Diapositiva | Idea para decir |
|---|---|---|
| 1 | Portada | Venimos a explicar por qué esta combinación, no a mostrar tecnologías. |
| 2 | Seis datos | Cada dato se pide distinto. Las tarjetas separan lo medido, lo propuesto y lo que no podemos afirmar. |
| 3 | Arquitectura | Una ruta termina en un solo adaptador. La API corre en la notebook y las bases en Docker. Prometheus observa la API y los exporters. |
| 4 | Un partido | Flujo de datos: el código `F2030-006` une los módulos, ninguna request combina dos bases. |
| 5 | Estructuras | Para cada base: qué estructura implementamos, qué consulta la motivó y qué trade-off aceptamos. |
| 6 | Cassandra | Partición por partido y bloque. Contar el precio y el hallazgo del reintento duplicado. |
| 7 | Garantías | Consistencia fuerte para el estado del partido; eventual para comentarios; TTL e invalidación con `DEL` en la caché. |
| 8 | Distribución | Primero lo que corre: un nodo por base. Después el diseño por regiones, aclarando que CAP no se midió. |
| 9 | En vivo | Correr los dos flujos y decir qué base responde y por qué el patrón es distinto. |
| 10 | Carga | 30 usuarios sobre las seis bases, 0 errores. Decir el límite: es una notebook. |
| 11 | Falla | Leer el panel: qué se cayó, qué siguió, cuándo avisó la alerta y qué decisión tomaríamos. |
| 12 | Hallazgos | Hito 12: el cuello estaba en la API. IRIS: `healthy` en Docker, caída para la API, sin causa comprobada. |
| 13 | Límites | Lo que no se midió y el costo de seis productos. Cuándo alcanzaría una relacional. |
| 14 | Cierre | Responder la pregunta central y decir qué mejoraríamos. |

## Frases que conviene evitar

- "Escala a nivel mundial": no lo medimos.
- "La aplicación funciona": hay que decir qué base responde y por qué.
- "Grafana muestra que está bien": hay que decir qué panel, qué valor y qué decisión tomaríamos si empeora.
- "Cassandra es AP, entonces no se cae": en el laboratorio tiene `replication_factor: 1`.

## Si el tiempo se acorta

Cortar en este orden: el segundo flujo de la demo, los detalles de InfluxDB y MongoDB (quedan para
preguntas), la mejora propuesta. Nunca cortar: qué no medimos y la pregunta central.

## Antes de la defensa

- [ ] Correr `defensa/demo.md` completo, una vez, en la máquina de la defensa.
- [ ] Sembrar Redis poco antes: la sesión de prueba vence a los 30 minutos.
- [ ] Tener abiertas las pestañas y la terminal con letra grande.
- [ ] Revisar que no haya credenciales a la vista.
- [ ] Tener la presentación y las capturas sin depender de internet.
