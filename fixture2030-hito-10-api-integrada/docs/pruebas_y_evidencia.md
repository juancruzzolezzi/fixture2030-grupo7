# Pruebas y evidencia

## Método

`tests/integration/` corre contra la API real (`http://localhost:8000`),
con las seis bases levantadas por `docker-compose.yml` de esta carpeta y
sembradas por `scripts/sembrar_datos.sh`. No hay mocks: cada aserción
depende de que el adaptador correspondiente haya llegado de verdad a su
fuente.

- `test_endpoints.py` (21 casos): por cada una de las 6 fuentes, al menos
  una operación válida, un parámetro inválido (400) y un recurso
  inexistente (404). Además cubre la agregación incorrecta de InfluxDB
  (400), la creación idempotente de Cassandra, la invalidación idempotente
  de Redis y la transición idempotente/conflictiva de IRIS.
- `test_dependencia_caida.py` (1 caso): para el contenedor de Redis con
  `docker compose stop redis`, confirma `503` con
  `tipo: dependencia_no_disponible`, y lo vuelve a levantar. Es la prueba
  de "dependencia detenida o inaccesible" que pide RF15 — provocada contra
  infraestructura real, no simulada.

## Resultado de la corrida

**22/22 pruebas pasaron.** Salida completa en `docs/evidencia/pytest.txt`;
conectividad de las 6 fuentes en `docs/evidencia/salud.txt`.

## Bugs reales que aparecieron al probar contra las bases reales (y no con mocks)

Vale la pena dejarlos anotados porque cada uno hubiera pasado inadvertido
sin una corrida real:

1. **Neo4j, variables entre sentencias.** El script de siembra encadenaba
   `MERGE (p:Partido {...})` en una sentencia y `MERGE (p)-[:REL]->(x)` en
   la siguiente, asumiendo que `p` seguía apuntando al mismo nodo. No es
   así: `cypher-shell --file` ejecuta cada sentencia separada por `;` de
   forma independiente, así que la segunda creaba un nodo `Partido` nuevo,
   vacío y sin `codigo`. Se corrigió re-matcheando por clave de negocio en
   cada sentencia (ver `scripts/neo4j/sembrar.cypher`).
2. **Cassandra, UUID en la respuesta.** `comentario_id` llega del driver
   como `uuid.UUID`, no como `str`; el schema de salida lo esperaba como
   string y Pydantic lo rechazaba con un 500. Se convierte explícitamente
   en el adaptador.
3. **Neo4j, tipo de fecha propio del driver.** `p.fecha` llega como
   `neo4j.time.Date`, un tipo que Pydantic tampoco reconoce. Mismo arreglo:
   convertir a string en el adaptador antes de que llegue al schema.
4. **InfluxDB, ventana horaria mal calculada a mano.** Los primeros puntos
   de prueba se cargaron con un epoch que correspondía a las 14:00 UTC en
   vez de las 18:00 UTC (el mismo horario que usan Mongo/Neo4j/Cassandra
   para este partido). La prueba de ventana devolvía una lista vacía, no
   un error: quedó como recordatorio de que una lista vacía puede ser un
   síntoma silencioso de un dato mal cargado, no solo una respuesta válida.
5. **IRIS, contraseña por vencer en el primer login real.** La imagen
   Community exige cambiar la contraseña de `_SYSTEM` la primera vez que
   algo se conecta por el puerto 1972 (no por la terminal local, que usa
   confianza del SO). Documentado y resuelto en
   `docs/conectividad_y_configuracion.md`.
6. **IRIS, `chown` sobre un bind mount.** El mismo problema que el Hito 9
   documenta para Windows ("Error executing chown irisowner:irisowner
   /durable/") apareció también en este host Linux. Se resolvió igual que
   ellos: un volumen administrado por Docker más un servicio `iris-init`
   que hace el `chown` una sola vez (ver `docker-compose.yml`).

Ninguno de estos seis problemas se hubiera visto con una prueba que
mockeara los adaptadores — es la razón por la que esta entrega se probó
contra las bases reales en todo momento, no solo al final.

## Rendimiento básico (RNF18)

Método: `curl -w "%{time_total}"`, 5 corridas por endpoint, API y bases en
el mismo host (notebook), sin carga concurrente — mide latencia de la capa
HTTP, no throughput. Resultado completo en `docs/evidencia/latencia.txt`.

| Endpoint | Fuente | Latencia (5 corridas) |
|---|---|---|
| `GET /equipos/{codigo}` | MongoDB | 4.7–6.0 ms |
| `GET /partidos/{codigo}/estadisticas` | InfluxDB (HTTP+SQL) | 25.1–26.9 ms |
| `GET /partidos/{codigo}/entidad-compleja` | IRIS (Native SDK) | 4.7–6.1 ms |

InfluxDB es más lento que los demás porque el adaptador habla HTTP contra
`/api/v3/query_sql` (una llamada de red adicional dentro de la misma
notebook), mientras que Mongo e IRIS usan sus drivers nativos sobre TCP
directo. Ninguno de los tres se acerca a un límite preocupante para uso
interactivo; no se midió throughput bajo carga concurrente porque ese tipo
de medición ya se hizo, por fuente, en los Hitos 6 y 8 — acá se mide la
capa de integración, no se repite esa prueba.
