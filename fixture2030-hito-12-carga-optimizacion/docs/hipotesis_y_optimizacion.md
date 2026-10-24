# Hipótesis y optimización

## Problema observado

En la línea base, `leer_estadisticas` es la operación más lenta por lejos
aunque la consulta es chica (300 puntos de una sola serie). Además:

- la CPU de la API es la más alta de todo el sistema (cerca o por encima de un
  núcleo entero), mientras que el contenedor de InfluxDB casi no trabaja;
- las otras dos operaciones, que van a Cassandra, también empeoran cuando hay
  estadísticas en la mezcla, aunque Cassandra no está exigida.

Si el límite estuviera en InfluxDB, veríamos su contenedor ocupado. Si
estuviera en el generador, veríamos su CPU alta y operaciones atrasadas. No
pasa ninguna de las dos cosas: el trabajo se está haciendo dentro del proceso
de la API.

## Hipótesis

El adaptador de InfluxDB del Hito 10 consulta con `httpx.post(...)`. Esa
función crea un `httpx.Client` nuevo en cada llamada y lo descarta. Crear un
cliente arma un contexto SSL y carga los certificados, aunque la URL sea
`http://`. Eso es CPU pura de Python y retiene el GIL. Por eso frena también a
los otros threads de la API, incluidos los que atienden comentarios. Encima,
cada consulta abre una conexión TCP nueva con InfluxDB.

## Prueba de la hipótesis (antes de cambiar nada)

`scripts/probar_hipotesis.py` mide, fuera de la API y sin concurrencia, tres
cosas: crear un cliente solo, la consulta del flujo con un cliente nuevo cada
vez, y la misma consulta con un cliente reutilizado. Resultado en
`evidencia/prueba_hipotesis.txt`.

Si la hipótesis es correcta:

- crear el cliente tiene que costar casi lo mismo que la consulta completa con
  cliente nuevo;
- con el cliente reutilizado, la consulta tiene que bajar a pocos milisegundos.

Eso es lo que medimos: el costo está en crear el cliente, no en InfluxDB.

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

Ver `evidencia/comparacion.md` y `evidencia/grafico_p95.svg`. Lo que hay que
mirar:

- **leer_estadisticas**: el p95 y el p99 tienen que bajar mucho, porque es la
  operación donde estaba el costo.
- **leer_comentarios y publicar_comentario**: bajan el p95 y el p99 sin haber
  tocado Cassandra. Coincide con la explicación del GIL: la API deja de gastar
  CPU en crear clientes y le queda para atender el resto. La mediana (p50) de
  estas dos no cambia de forma consistente: entre nuestras corridas se movió
  unos pocos ms para arriba o para abajo. A esta escala lo tomamos como ruido,
  no como mejora ni como empeoramiento.
- **CPU de la API**: baja fuerte a la misma tasa de operaciones.
- **Throughput**: igual en las dos corridas, porque las dos alcanzan las
  60 ops/s objetivo. La mejora a esta carga no es "más ops/s" sino la misma
  carga con mucha menos latencia y CPU. Ese margen es el que permitiría
  atender más usuarios con la misma notebook, pero no lo afirmamos como
  medido: no corrimos la prueba de capacidad máxima (ver limitaciones).
- **Errores e integridad**: sin cambios (0 errores en ambas, mismas
  verificaciones en OK).

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
  quedan cerradas del otro lado. httpx las descarta y abre otras. Lo probamos
  con el escenario `influxdb pausar` del Hito 11: la API vuelve a responder
  200 sola.
- **Complejidad**: unas 20 líneas más y una variable de configuración.

## Alternativas que descartamos

| Alternativa | Por qué no |
|---|---|
| Cachear las estadísticas en Redis | Ataca el síntoma: la primera consulta seguiría pagando los ~30 ms. Agrega invalidación y datos viejos en una pantalla en vivo. |
| Más procesos de uvicorn (`--workers 4`) | Reparte el mismo desperdicio en más núcleos. La notebook ya tiene las bases corriendo; más procesos compiten con ellas. |
| Cambiar la consulta SQL o agregar índices en InfluxDB | La prueba aislada muestra que la consulta tarda pocos ms. No es donde está el problema. |

## Decisión

Lo dejamos: `INFLUX_REUSAR_CLIENTE=1` es el valor por defecto en
`.env.example`. Quedan pendientes, para un próximo paso, la prueba de
capacidad y el hallazgo de integridad de los reintentos (ver
`integridad_y_limitaciones.md`).
