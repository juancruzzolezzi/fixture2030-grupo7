# Guion de la defensa (máximo 20 minutos)

Hay que ensayarlo con cronómetro y repartir los bloques (completar "Quién"). Todos tienen que poder
responder sobre cualquier módulo. Dejar 20 s de margen en cada cambio de orador.

| Tiempo | Bloque | Quién | Qué decir | Con qué |
|---|---|---|---|---|
| 0:00-2:00 | **Inicio** | ___ | El problema de la FIFA: 127 partidos, seis tipos de dato con accesos incompatibles. La decisión: un modelo por patrón de acceso, unidos por código. Y el aviso: mostramos lo medido y separamos lo que es diseño. | Diapositivas 1-2 |
| 2:00-5:00 | **Arquitectura** | ___ | Recorrido: qué guarda cada base y por qué no una sola. Cada ruta termina en un adaptador. | Diapositivas 3-4 |
| 5:00-11:00 | **Decisiones** | ___ y ___ | Tres casos a fondo: partición de Cassandra, consistencia fuerte en IRIS, TTL e invalidación en Redis. Después distribución y CAP: qué es laboratorio y qué es diseño. | Diapositivas 5-8 |
| 11:00-14:00 | **Operación** | ___ | Dos flujos: comentarios (partición) contra eventos (recorrido). Decir qué base responde y por qué el patrón es distinto. | `defensa/demo.md`, flujos 1 y 2 |
| 14:00-18:00 | **Evidencia** | ___ | Leer el panel: qué significa cada fila. Mostrar la falla de Redis, antes preparada: qué se cayó y qué siguió. Contar el hallazgo del Hito 12 con números. | Grafana y diapositivas 9-10 |
| 18:00-20:00 | **Cierre** | ___ | Por qué es adecuada, qué trade-offs aceptamos, qué no medimos y qué haríamos después. Responder la pregunta central. | Diapositivas 11-12 |

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
