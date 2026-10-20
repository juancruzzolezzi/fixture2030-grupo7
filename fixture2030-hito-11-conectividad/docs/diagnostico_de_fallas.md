# Diagnóstico de fallas

## Tipos de falla de red

| Resultado | Qué significa | Dónde lo vimos |
|---|---|---|
| Conexión OK | hay algo escuchando en ese puerto (todavía no sabemos si es la base correcta) | todas las bases en `resultados_tcp.txt` |
| Connection refused | el host responde pero no hay nadie en ese puerto (contenedor detenido o puerto equivocado) | Redis e IRIS detenidos |
| Timeout | no hubo respuesta en el tiempo límite (red, firewall o proceso congelado) | InfluxDB pausado: el TCP conecta pero la consulta no vuelve |
| Host no resuelto | el nombre no existe desde este entorno | `mongodb:27017` desde la notebook |
| Puerto incorrecto | conecta, pero responde otro producto | PING de Redis al puerto de Mongo |

## Escenarios que corrimos

Los tres se corren con `scripts/escenario_falla.sh` y no borran volúmenes. La
salida completa, con los request_id y las líneas de log, está en
`evidencia/escenario_<servicio>.txt`.

### 1. Redis detenido

- Hipótesis: si se cae Redis, `/sesiones/{id}` tiene que devolver un error claro
  rápido, sin colgarse y sin afectar al resto de la API.
- Cambio: `docker compose stop redis`.
- Qué esperamos: 503 `dependencia_no_disponible` en menos de 1 s, `/salud`
  marca redis `down` y el estado general `degraded`, `/equipos/ARG` sigue en 200.
  En el log de la API queda el detalle técnico (`ConnectionError`), que no
  aparece en la respuesta.
- Recuperación: `docker compose start redis`. La ruta vuelve a dar 200 y la
  sesión de prueba sigue estando, porque los datos están en el volumen nombrado.
- Siguiente paso: nada que corregir. En producción convendría una alerta si la
  readiness queda en `degraded` mucho tiempo.

### 2. InfluxDB pausado (timeout)

- Hipótesis: con el proceso congelado, el puerto sigue aceptando conexiones TCP.
  La API no tiene que quedarse esperando para siempre.
- Cambio: `docker compose pause influxdb`.
- Qué esperamos: 504 `timeout_dependencia` a los ~3 s (el `INFLUX_TIMEOUT_S`).
  El resto de la API sigue respondiendo.
- Recuperación: `docker compose unpause influxdb`, la ruta vuelve a 200 y los
  puntos siguen estando.
- Siguiente paso: si en el Hito 12 aparecen 504 de Influx, primero hay que
  revisar si el servicio está saturado, porque la red funciona.

### 3. IRIS reiniciado

- Hipótesis: después de que IRIS se reinicia, la API tiene que volver a
  conectarse sola.
- Lo que pasaba antes: la API del Hito 10 guardaba la conexión a IRIS para
  siempre. Después de un reinicio seguía devolviendo 503 "IRIS no respondió a
  tiempo" hasta que reiniciábamos la API, aunque IRIS ya estuviera arriba.
  Además, el mensaje confundía: no era un timeout, el socket estaba muerto.
- Cambio en la API: si falla, se descarta la conexión y la próxima request
  conecta de nuevo (`iris_adapter.py`).
- Qué esperamos ahora: 503 mientras está detenido y 200 unos segundos después
  del `docker compose start iris`, sin reiniciar la API.

## Otras cosas que encontramos y corregimos en la API

- Redis caído tardaba ~4,8 s en devolver el 503 con un timeout de 2 s, porque
  redis-py reintenta 3 veces por defecto. Ahora reintenta una sola vez.
- Una password incorrecta de Neo4j aparecía como "Neo4j no respondió a tiempo".
  Ahora dice que rechazó las credenciales.
- Un timeout y una base caída devolvían lo mismo. Ahora son 504 y 503.
- MongoDB tarda los 3 s del timeout en devolver el 503 aunque la conexión se
  rechace enseguida, porque pymongo sigue intentando hasta que se vence. No es
  un error, pero conviene tenerlo en cuenta para el Hito 12.
