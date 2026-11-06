# Hallazgo: IRIS "healthy" que no aceptaba conexiones

Observado el 05/11/2026 en la notebook del grupo (Windows 11, 16 CPU, Docker Desktop), commit a57f521,
horas después de un apagado inesperado de la notebook. No sabemos si ese apagado fue la causa: no
intentamos reproducirlo.

**Qué pasó.** El contenedor figuraba sano, pero las 480 requests de IRIS de la carga dieron 503.

| Señal | Valor |
|---|---|
| `docker ps` | `h10-iris | Up 12 minutes (healthy)` |
| `database_up{database="iris"}` | 0, con `BaseDeDatosCaida(iris)` en firing |
| `GET /partidos/{codigo}/entidad-compleja` en la carga | 480 de 480 con 503 |
| Las otras cinco bases | Respondieron, sin fallas en `database_errors_total` |
| Error en `api.log` | `<COMMUNICATION LINK ERROR> Failed to connect to server ... remote disconnect, recv() returned 0` |
| Log de IRIS al arrancar | `[Generic.Event] Super Server exited due to SIGTERM received` |
| Control del puerto 1972 en `/proc/net/tcp` | 0 líneas en LISTEN. No revisamos `/proc/net/tcp6`, así que por sí solo no es concluyente |

**Qué lo resolvió.** `docker compose restart iris`, sin borrar el volumen. Al minuto, `/salud?forzar=true` dio
`iris: up` y `/entidad-compleja` devolvió el partido, sin reiniciar la API.

**Qué concluimos**

- El healthcheck del contenedor no prueba el camino que usa la API. La métrica `database_up` sí, y por eso avisó.
- Una base caída no arrastró a las demás: la API siguió atendiendo cerca de 56 ops/s.
- **Inferido, no comprobado**: el Super Server, que atiende el puerto 1972, habría quedado abajo. Los registros son
  compatibles con eso, pero no llegamos a la causa de fondo.

**Mejora propuesta**: un healthcheck de IRIS que pruebe una conexión al puerto 1972. Mientras tanto,
`scripts/generar_evidencia.py` no da por completa una corrida si alguna de las seis bases no está arriba.
