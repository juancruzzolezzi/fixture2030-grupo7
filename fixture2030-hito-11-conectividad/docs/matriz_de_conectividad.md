# Matriz de conectividad

La matriz la arma el script al final de cada corrida, a partir de lo que
realmente se probó: `evidencia/matriz.md`. Si una base no se probó, queda como
"no probado" o "desconocido". No la completamos a mano.

Estados:

| Estado | Significa |
|---|---|
| disponible | todas las pruebas que se corrieron dieron OK |
| degradado | la base responde a su cliente pero falla la ruta de la API |
| no disponible | falló alguna capa (TCP, protocolo, credenciales, contexto o lectura) |
| desconocido | solo se probó TCP; con eso no alcanza para decir que funciona |
| no probado | no se corrió ninguna prueba |

Columnas de la matriz: TCP (configuración + DNS + puerto), Cliente/driver
(protocolo, credenciales, contexto y lectura con el driver de cada base y con
su cliente de línea de comandos), API (las rutas del Hito 10). El detalle de
cada prueba, con fecha, tiempo y resultado, está en
`evidencia/resultados_tcp.txt`, `resultados_clientes.txt` y `resultados_api.txt`.

## Qué prueba cada capa (y qué no)

| Capa | Responde | Todavía no dice |
|---|---|---|
| DNS | si el nombre existe desde este entorno | si hay alguien escuchando |
| TCP | si hay un proceso escuchando en ese puerto | si es la base correcta |
| Protocolo | si habla el protocolo esperado (hello, Bolt, CQL, PING, HTTP) | si las credenciales sirven |
| Autenticación | si el usuario/token es aceptado | si existe la base que usa la API |
| Contexto | si existe la base, keyspace o namespace | si hay datos |
| Lectura | si se puede leer un dato de prueba, acotado | si la ruta de la API funciona |
| API | si funciona todo el camino HTTP -> API -> base | rendimiento (Hito 12) |

Algunas cosas que vimos al correrlo:

- MongoDB no da error si la base no existe: devuelve una lista vacía, porque
  crea las bases recién cuando se escribe. Por eso en "contexto" miramos que
  estén las colecciones `equipos` y `jugadores`.
- InfluxDB 3 responde 401 en `/health` si no se manda el token. Eso significa
  que está vivo y protegido, no que esté caído.
- Mandar un PING de Redis al puerto de Mongo conecta por TCP pero no contesta:
  un puerto abierto no garantiza que sea el producto correcto.
