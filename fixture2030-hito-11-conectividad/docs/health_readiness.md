# Health y readiness

Agregamos estos endpoints a la API del Hito 10 (`app/main.py`):

| Endpoint | Para qué | Toca las bases | Respuesta |
|---|---|---|---|
| `GET /salud/vivo` | liveness: el proceso de la API responde | no | siempre 200 `{"estado": "up"}` |
| `GET /salud/listo` | readiness: si puede recibir tráfico | sí | 200 `up` o `degraded`, 503 `down` |
| `GET /salud` | detalle por dependencia: estado y milisegundos | sí | 200 con el estado de cada base |

Estados:

- `up`: la prueba de esa base terminó bien.
- `down`: se intentó y falló.
- `degraded` (solo en el estado general): alguna base está caída pero otras no.

Si se cae una sola base, la API no pasa a `down`. Las rutas de esa base ya
devuelven 503/504, y el resto de los módulos sigue funcionando. En el escenario
de Redis caído, `/equipos/ARG` siguió dando 200. Sacar la API del balanceador
por una sola base no arreglaría nada.

## Frecuencia y costo

- El chequeo hace una operación chica por base (ping, `verify_connectivity`,
  `SELECT 1`, etc.). Las 6 corren en paralelo, así que una base colgada no suma
  su timeout al de las demás.
- El resultado se guarda 10 segundos. Aunque algo consulte `/salud/listo` cada
  segundo, las bases reciben como mucho un chequeo cada 10 s. La contra es que
  durante esos 10 s puede mostrar el estado anterior.
- `GET /salud?forzar=true` ignora el resultado guardado (lo usamos en los
  escenarios de falla).
- Las requests normales de la API nunca disparan este chequeo.

## Timeouts

| Base | Timeout | Reintentos |
|---|---|---|
| MongoDB | 3 s (`serverSelectionTimeoutMS`) | pymongo reintenta hasta que vence el timeout |
| Neo4j | 3 s (conexión y obtener conexión del pool) | no |
| Cassandra | 3 s (conexión y consultas) | los del driver |
| Redis | 2 s | 1 (antes eran 3 por defecto y el 503 tardaba ~4,8 s) |
| InfluxDB | 3 s | no |
| IRIS | 3 s (antes no tenía y el SDK espera 10 s) | no |

Estos son los timeouts **configurados**. La duración total de una request puede
ser algo mayor (conexión, reintento, armado de la respuesta); la que medimos en
cada caso está en `evidencia/escenario_*.txt`.

Si una base no responde dentro del timeout, la API devuelve 504
`timeout_dependencia`. Si rechaza la conexión, devuelve 503
`dependencia_no_disponible`. Antes las dos cosas eran 503 con el mismo mensaje.
