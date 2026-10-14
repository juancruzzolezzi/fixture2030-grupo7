# Contratos y errores

El contrato completo (rutas, parametros, schemas, codigos) vive en
`openapi/openapi.yaml`, generado desde la propia aplicacion FastAPI (no
escrito a mano aparte: `scripts/exportar_openapi.py` lo vuelca a archivo
despues de cada cambio, para que nunca describa un endpoint que no existe).
Con la API corriendo, Swagger UI queda en `http://localhost:8000/docs`.

## Mapa de endpoints

| Ruta | Metodo | Fuente | Operacion | Caso de uso |
|---|---|---|---|---|
| `/equipos` | GET | MongoDB | Listar con filtro/paginado | 1 |
| `/equipos/{codigo}` | GET | MongoDB | Recuperar por clave | 1 |
| `/equipos/{codigo}/jugadores` | GET | MongoDB | Listar con filtro/paginado | 1 |
| `/jugadores/{codigo}` | GET | MongoDB | Recuperar por clave | 1 |
| `/partidos/{codigo}` | GET | Neo4j | Patron de grafo | 2 |
| `/partidos/{codigo}/eventos` | GET | Neo4j | Recorrido de 2 relaciones | 2 |
| `/partidos/{codigo}/comentarios` | GET | Cassandra | Lectura por particion | 3 |
| `/partidos/{codigo}/comentarios` | POST | Cassandra | Creacion idempotente | 3 |
| `/sesiones/{usuario_id}` | GET | Redis | Lectura de Hash + TTL | 4 |
| `/partidos/{codigo}/cache` | GET | Redis | Lectura de String | 4 |
| `/partidos/{codigo}/cache` | DELETE | Redis | Invalidacion idempotente | 4 |
| `/partidos/{codigo}/estadisticas` | GET | InfluxDB | Ventana temporal | 5 |
| `/partidos/{codigo}/estadisticas/agregacion` | GET | InfluxDB | Agregacion validada | 5 |
| `/partidos/{codigo}/entidad-compleja` | GET | IRIS | Objeto navegado | 6 |
| `/partidos/{codigo}/estado` | PATCH | IRIS | Transicion de estado | 6 |
| `/salud` | GET | las 6 | Conectividad real | — |

## Formato de error (unico para toda la API)

```json
{
  "error": {
    "tipo": "no_encontrado",
    "mensaje": "No existe un equipo con codigo 'ZZZ'.",
    "request_id": "3f1a9c3e-...-...-...-..."
  }
}
```

| `tipo` | HTTP | Ejemplo real |
|---|---|---|
| `validacion` | 400 | `desde` no es ISO 8601; `bloque_horario` no tiene el formato `AAAAMMDDHHmm`; `confederacion` fuera de la lista. |
| `no_encontrado` | 404 | Codigo de equipo/partido/jugador inexistente; sesion ausente o expirada; cache miss. |
| `conflicto` | 409 | `PATCH /partidos/{codigo}/estado` con una transicion que `Partido.CambiarEstado` rechaza. |
| `dependencia_no_disponible` | 503 | La base correspondiente no responde (contenedor caido, timeout de red). |
| `error_interno` | 500 | Cualquier excepcion no prevista. El mensaje nunca incluye la excepcion original. |

## Idempotencia (RF19, RNF14)

| Operacion | Comportamiento ante reintento |
|---|---|
| Todos los `GET` | Sin efectos, cualquier cantidad de reintentos es segura. |
| `POST /partidos/{codigo}/comentarios` | Requiere `clave_idempotencia` del cliente. El `comentario_id` se deriva de `(partido, bloque, clave)`: repetir la misma request sobreescribe la misma fila, no crea una nueva. |
| `DELETE /partidos/{codigo}/cache` | Invalidar algo ya invalidado devuelve `habia_valor: false`, no un error. |
| `PATCH /partidos/{codigo}/estado` | Pedir el estado que el partido ya tiene devuelve `sin_cambios: true` con 200, no un 409. |

## Por que 200 nunca significa "la dependencia funciono, seguro"

La API nunca traduce una falla de conexion a una lista vacia o a un `null`
silencioso. Una lista vacia real (por ejemplo, "este bloque todavia no tiene
comentarios") es un `200` legitimo; una Cassandra caida es siempre un `503`
con `tipo: dependencia_no_disponible`, nunca lo mismo. La diferencia se
prueba en `tests/integration/` apagando el contenedor correspondiente.
