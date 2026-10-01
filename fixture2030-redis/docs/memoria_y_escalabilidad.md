# Memoria y escalabilidad — Hito 7 (Redis) — Fixture 2030

## 1. Expiración y evicción responden a preguntas distintas

| | Expiración (TTL) | Evicción (maxmemory) |
|---|---|---|
| Pregunta que responde | ¿Cuánto tiempo este dato sigue siendo útil o seguro? | ¿Qué puedo descartar cuando no entra nada más en RAM? |
| Quién la decide | El diseño del producto, dato por dato | El servidor, bajo presión de memoria |
| Cuándo actúa | Al cumplirse el plazo | Al alcanzar el límite de memoria |
| Es previsible | Sí | No: depende de la carga |

Las dos pueden borrar una clave, pero por motivos distintos. **Un TTL no
garantiza que la clave sobreviva hasta ese instante**: con una política de
evicción activa, Redis puede sacarla antes si necesita memoria.

Esa es exactamente la razón por la que la caché de este módulo se diseñó para
poder reconstruirse (ver `ciclo_de_vida_e_invalidacion.md`) y por la que el
comportamiento ante una clave ausente está definido explícitamente.

## 2. Política elegida

```
CONFIG SET maxmemory 256mb
CONFIG SET maxmemory-policy volatile-lru
```

**`volatile-lru`**: sólo son candidatas a ser evictadas las claves que **ya
tienen expiración**, y entre ellas se descartan las usadas hace más tiempo.

### Por qué

El material advierte sobre esta política: *"exige disciplina: si no hay claves
con TTL, se comporta como noeviction"*. Este módulo cumple esa disciplina de
forma deliberada — **toda clave que se crea lleva TTL**, sin excepción:

| Clave | TTL |
|---|---|
| `fixture2030:sesion:*` | 1800 s |
| `fixture2030:cache:partido:*` | 60 s |
| `fixture2030:contador:*` | 86400 s |
| `fixture2030:encuesta:*` | 86400 s |
| `fixture2030:conectados:*` | 3600 s |
| `fixture2030:actividad:*` | 1800 s |

Como todo tiene TTL, en la práctica el conjunto de candidatas es el keyspace
completo, y `volatile-lru` se comporta como `allkeys-lru` — con una diferencia
que importa: **si alguien creara una clave sin TTL, quedaría protegida de la
evicción**. Eso convierte la política en una red de seguridad: una clave sin
criterio temporal es un defecto de diseño, y esta configuración hace que ese
defecto no se lleve puesto nada más.

### Qué se descartó

| Política | Por qué no |
|---|---|
| `noeviction` | Al llenarse la memoria, Redis devuelve error en las escrituras. Eso cortaría la creación de sesiones y la votación en el peor momento: el pico de un partido. Para un módulo cuyo contenido es transitorio, romper es peor que descartar. |
| `allkeys-lru` | Funciona bien en una instancia dedicada sólo a caché. Acá la instancia mezcla caché con sesiones, y esta política no distingue entre una clave con criterio temporal y una sin él. |
| `allkeys-lfu` | Defendible, porque unos pocos partidos concentran el tráfico y conviene conservar sus fichas. Pero prioriza por frecuencia histórica, y una sesión recién creada es poco frecuente por definición: quedaría entre las primeras candidatas. |
| `volatile-ttl` | Prioriza las claves a las que les queda menos tiempo, o sea las fichas de partido (TTL 60 s). Como son justamente las más consultadas, las estaría descartando en el peor momento. |

## 3. Qué efecto tendría la evicción sobre cada dato

| Dato | Si es evictado | Gravedad |
|---|---|---|
| Ficha de partido (caché) | Se reconstruye sola en el próximo miss | Baja: sólo latencia |
| Contador de visitas | Se pierde el acumulado de la jornada | Baja: es una métrica, no un dato de negocio |
| Conectados / actividad | Se pierde el estado temporal | Baja: se repuebla con la actividad siguiente |
| Votación (ranking) | Se pierden los votos de ese partido | **Media**: no es reconstruible desde ninguna fuente |
| Sesión | El usuario tiene que autenticarse de nuevo | **Media**: molesta al usuario, no pierde datos del torneo |

Los dos casos de gravedad media son los que habría que revisar si el módulo
creciera: la votación es el único dato que nace y muere en Redis sin respaldo
en ningún otro módulo. Si el producto decidiera que esos votos importan
después del partido, habría que persistirlos en la fuente de verdad y tratar
la clave de Redis como una copia acelerada, igual que la ficha.

## 4. Persistencia del laboratorio

El Compose usa snapshot RDB (`--save 60 1`) y monta los datos en
`~/docker/data/redis`. Con eso, `docker compose stop` o `down` no borran el
trabajo de práctica.

Aclaración importante: **persistir Redis no convierte una clave derivada en
fuente autoritativa**. Que la caché sobreviva a un reinicio es una comodidad
del laboratorio, no un cambio en quién es dueño del dato.

Un RDB puede perder los cambios posteriores a la última foto si el proceso
termina de golpe. Para este módulo es aceptable: lo que se perdería son
sesiones y estado temporal, exactamente los datos que el diseño ya asume como
descartables.

## 5. Un nodo no es una topología de alta disponibilidad

El contenedor de la notebook es **un único nodo**. Sirve para entender el
modelado, las operaciones y el ciclo de vida, pero no prueba:

- conmutación ante fallas,
- distribución real de claves,
- ni consistencia entre réplicas.

| Topología | Qué resolvería | Trade-off |
|---|---|---|
| **Standalone** (este laboratorio) | Nada: es para aprender y probar | Punto único de falla, límite de RAM y CPU de una máquina |
| **Primary + réplicas** (con Sentinel) | Lecturas repartidas y recuperación ante caída del primary | Las réplicas pueden estar brevemente atrasadas; las escrituras siguen concentradas |
| **Redis Cluster** | Reparte las claves en slots y permite sumar nodos para capacidad y escritura | Una operación sobre varias claves exige que estén en el mismo slot |

Si este módulo tuviera que sostener el tráfico real del Mundial, el orden de
los cambios sería: primero réplicas de lectura (porque el patrón dominante es
lectura de sesión y de ficha), y recién después Cluster, cuando el límite
pasara a ser la memoria o la escritura de una sola máquina.

Un detalle propio de Cluster que el diseño actual no necesita: si dos claves
tuvieran que operarse juntas de forma atómica, habría que forzarlas al mismo
slot. En este modelo cada operación atómica toca **una sola clave**, salvo el
`MULTI`/`EXEC` de la votación, que sería el único punto a revisar en una
migración a Cluster.
