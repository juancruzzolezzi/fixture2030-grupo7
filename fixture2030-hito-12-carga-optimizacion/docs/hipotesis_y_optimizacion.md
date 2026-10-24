# Hipótesis y optimización

## Problema observado

En la línea base (`evidencia/resultados_linea_base.txt`, Windows 11, 8 CPU
lógicas, commit a6609bb):

- `leer_estadisticas` tarda 1.681 ms de mediana y 2.767 ms de p95, aunque la
  consulta es chica (300 puntos de una sola serie). Las lecturas de
  comentarios tardan 21 ms de mediana.
- La API no llega a la tasa pedida: atiende 39,3 de las 60 ops/s, y 579
  operaciones salieron tarde porque la anterior todavía no había respondido.
- La CPU de la API promedia 556 % (más de 5 núcleos). El contenedor de
  InfluxDB usa 9 % y el generador 15 %.

Si el límite estuviera en InfluxDB, veríamos su contenedor ocupado. Si
estuviera en el generador, veríamos su CPU alta. No pasa ninguna de las dos
cosas: el trabajo se está haciendo dentro del proceso de la API, y en la ruta
de estadísticas.

## Hipótesis

El adaptador de InfluxDB del Hito 10 consulta con `httpx.post(...)`. Esa
función crea un `httpx.Client` nuevo en cada llamada y lo descarta. Crear un
cliente arma un contexto SSL y carga los certificados, aunque la URL sea
`http://`. Si eso es caro, cada consulta de estadísticas gasta CPU de la API
antes de llegar a InfluxDB, y los threads de la API compiten por esa CPU
(y por el GIL de Python) con los que atienden comentarios. Encima, cada
consulta abre una conexión TCP nueva con InfluxDB.

## Prueba de la hipótesis (antes de cambiar nada)

`scripts/probar_hipotesis.py` mide, fuera de la API y sin concurrencia, tres
cosas: crear un cliente solo, la consulta del flujo con un cliente nuevo cada
vez, y la misma consulta con un cliente reutilizado. Resultado en
`evidencia/prueba_hipotesis.txt`.

Si la hipótesis es correcta:

- crear el cliente tiene que costar casi lo mismo que la consulta completa con
  cliente nuevo;
- con el cliente reutilizado, la consulta tiene que bajar a pocos milisegundos.

Lo que medimos en la notebook:

| Caso | p50 | p95 |
|---|---|---|
| Crear `httpx.Client()` sin consultar | 249,3 ms | 352,5 ms |
| Consulta con cliente nuevo (como el Hito 10) | 244,3 ms | 298,4 ms |
| Consulta con cliente reutilizado | 4,9 ms | 24,4 ms |

Crear el cliente cuesta lo mismo que la consulta entera: el tiempo no está en
InfluxDB, está en crear el cliente. Con unas 8 consultas de estadísticas por
segundo, eso son unos 2 segundos de trabajo por segundo solo en crear
clientes. Alcanza para explicar la cola de la línea base.

## Cambio implementado

| | |
|---|---|
| Archivo | `fixture2030-hito-10-api-integrada/app/adapters/influx_adapter.py` (y una variable en `app/config.py`) |
| Cambio | Un único `httpx.Client` para todo el proceso, creado la primera vez que se usa, con un pool de hasta 20 conexiones keep-alive. `httpx.Client` se puede usar desde varios threads. |
| Cómo se activa | `INFLUX_REUSAR_CLIENTE=1`, el valor por defecto desde este hito. Con `0` la API se comporta exactamente como en el Hito 10, que es lo que usa la línea base. |
| Qué no cambia | El SQL, la validación, los timeouts, el contrato HTTP y la traducción de errores (503/504). |

Usamos una variable en lugar de dos versiones del código para que las dos
corridas usen el mismo commit, y para que cualquiera pueda repetir la
comparación con un solo comando.

## Resultado medido

Detalle en `evidencia/comparacion.md` y `evidencia/grafico_p95.svg`. Mismo commit,
mismo escenario y misma notebook; solo cambia `INFLUX_REUSAR_CLIENTE`.

| Sostenimiento (60 s) | Línea base | Optimizada |
|---|---|---|
| ops correctas por segundo (objetivo 60) | 39,3 | 60,0 |
| operaciones atrasadas | 579 | 0 |
| leer_estadisticas p50 / p95 / p99 (ms) | 1.681 / 2.767 / 3.196 | 13,6 / 29,0 / 53,2 |
| leer_comentarios p50 / p95 / p99 (ms) | 20,8 / 34,3 / 71,2 | 20,3 / 26,7 / 49,3 |
| publicar_comentario p50 / p95 / p99 (ms) | 33,6 / 55,2 / 90,1 | 23,6 / 38,6 / 49,6 |
| errores | 0 | 0 |
| CPU de la API (promedio) | 556 % | 23 % |

Cómo lo leemos:

- **Estadísticas**: la mediana baja de 1,7 s a 14 ms. Era la operación donde
  estaba el costo, y coincide con la prueba aislada.
- **Throughput**: en la línea base la API estaba saturada (39,3 de 60 ops/s,
  579 operaciones atrasadas). Optimizada atiende las 60 ops/s pedidas sin
  atrasos. Como cada usuario espera su respuesta, cuando la API tardaba, los
  usuarios mandaban menos operaciones. Por eso la línea base hizo 2.358
  operaciones y la optimizada 3.599 en el mismo minuto.
- **Comentarios**: no tocamos Cassandra, pero bajan las colas (p95 y p99), y
  la mediana de publicar baja de 34 a 24 ms. La mediana de leer comentarios
  queda igual (21 → 20 ms). La API deja de gastar CPU en crear clientes, y
  las requests de comentarios ya no esperan detrás de ese trabajo.
- **CPU**: la de la API baja de 556 % a 23 % aunque atiende un 50 % más de
  operaciones.
- **Cassandra**: su CPU promedio también bajó (74 % → 25 %) aunque recibió
  más operaciones. No lo podemos explicar con certeza. En Windows, Docker
  corre las bases en una VM que comparte los núcleos con la API: con la API
  ocupando más de 5 núcleos, todo compite. Lo dejamos anotado como observado,
  no como efecto del cambio.
- **Errores e integridad**: 0 errores en las dos, y las mismas verificaciones
  en OK (ver `integridad_y_limitaciones.md`).

## Trade-offs del cambio

- **Estado compartido**: el cliente vive todo lo que vive el proceso. Si
  cambia el token de InfluxDB hay que reiniciar la API. Antes también hacía
  falta, porque el token se lee del `.env` al arrancar.
- **Límite del pool**: con más de 20 consultas simultáneas a InfluxDB, las
  que sobran esperan una conexión libre. Si no la consiguen antes del timeout
  (3 s), la API responde 504. Antes no había ese límite, pero cada consulta
  abría su propia conexión sin control. Ahora el máximo está declarado.
- **Conexiones abiertas**: la API deja hasta 20 conexiones abiertas contra
  InfluxDB aunque no haya tráfico. Es poco para InfluxDB, pero es un recurso
  que antes no se ocupaba.
- **Reinicio de InfluxDB**: si InfluxDB se reinicia, las conexiones guardadas
  quedan cerradas del otro lado. Lo probamos con `docker restart h10-influxdb`:
  la primera consulta después del reinicio dio 503 y las siguientes 200, sin
  reiniciar la API. Con el escenario `influxdb pausar` del Hito 11, que
  volvimos a correr con este cambio, la API da 504 durante la pausa y vuelve
  a 200 sola.
- **Complejidad**: unas 20 líneas más y una variable de configuración.

## Alternativas que descartamos

| Alternativa | Por qué no |
|---|---|
| Cachear las estadísticas en Redis | Ataca el síntoma: cada consulta que no esté en caché seguiría pagando los ~250 ms de crear el cliente. Agrega invalidación y datos viejos en una pantalla en vivo. |
| Más procesos de uvicorn (`--workers 4`) | Reparte el mismo desperdicio en más núcleos. La notebook ya tiene las bases corriendo; más procesos compiten con ellas. |
| Cambiar la consulta SQL o agregar índices en InfluxDB | La prueba aislada muestra que la consulta tarda pocos ms. No es donde está el problema. |

## Decisión

Lo dejamos: `INFLUX_REUSAR_CLIENTE=1` es el valor por defecto en
`.env.example`. Quedan pendientes, para un próximo paso, la prueba de
capacidad de la versión optimizada y el hallazgo de integridad de los
reintentos (ver `integridad_y_limitaciones.md`).
