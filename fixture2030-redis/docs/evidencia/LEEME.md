# Evidencia — Hito 7 (Redis) — Fixture 2030

Grupo 7 — Ingeniería de Datos II

Todos los valores de este documento provienen de una ejecución real en la
notebook del grupo. No hay cifras estimadas ni extrapoladas.

## 1. Ambiente de la ejecución (RNF10)

| Dato | Valor |
|---|---|
| Fecha de ejecución | 30 de septiembre de 2026 |
| Versión de Redis observada | **8.10.2** (de `INFO server`) |
| Imagen | `redis:latest` |
| Topología | 1 nodo local en Docker Desktop (no es un cluster) |
| Persistencia | Snapshot RDB (`--save 60 1`), montado en `~/docker/data/redis` |
| Sistema operativo | Windows |
| CPU | AMD Ryzen 7 5700U — 8 núcleos / 16 hilos |
| Memoria RAM total | 33,7 GB |
| `maxmemory` configurado | 256 MB |
| `maxmemory-policy` | `volatile-lru` |
| `used_memory` al iniciar | 1.41 MB |

## 2. Capturas

| Archivo | Qué muestra | Requisito |
|---|---|---|
| `01_ambiente.png` | `docker compose ps` con el contenedor arriba y `PING` → `PONG` | RF1 |
| `02_version.png` | `INFO server` con `redis_version:8.10.2` | RNF10 |
| `03_memoria.png` | Los dos `CONFIG SET` y el `INFO memory` con `maxmemory_human:256.00M` y `maxmemory_policy:volatile-lru` | RF10 |
| `04_carga.png` | Verificación de las cinco estructuras cargadas, con sus TTL corriendo | RF11 |
| `05_sesion_ttl.png` | El TTL bajando 59 → 47 y quedando en 47 tras `HSET` | RF4 |
| `06_sesion_renovada.png` | `MULTI`/`EXEC` de renovación: TTL de vuelta en 1800 y `paginas_vistas` en 1 | RF3, RF4 |
| `07_sesion_expirada.png` | `TTL` en `-2`, `HGETALL` vacío y `HGET` sobre un usuario inexistente en `(nil)` | RF4 |
| `08_cache.png` | Miss → `SETEX` → hit → `DEL` → miss | RF6, RF7 |
| `09_concurrencia.png` | `INCR`/`INCRBY` llegando a 4552 y Top 3 del ranking | RF8, RF9 |
| `10_multi_exec.png` | `MULTI`/`EXEC` combinando voto, actividad y renovación de sesión | RF8 |
| `11a_stats_antes.png` | `INFO stats` inicial: `keyspace_hits:18`, `keyspace_misses:5` | RF12 |
| `11b_secuencia.png` | Los 12 `GET` de la secuencia controlada (8 con valor, 4 en `(nil)`) | RF12 |
| `11c_stats_despues.png` | `INFO stats` final: `keyspace_hits:26`, `keyspace_misses:9` | RF12 |
| `12_scan.png` | `SCAN` con cursor y `MATCH`, iterado hasta que el cursor vuelve a `0` | RNF8 |

## 3. Medición (RF12)

### Método

Se anotaron los contadores de `INFO stats`, se ejecutó una secuencia
**conocida** de 12 lecturas —8 sobre claves existentes y 4 sobre claves
ausentes— y se volvieron a leer los contadores. La diferencia entre ambas
mediciones es el resultado: no se estimó ni se extrapoló ningún valor.

El script está en `scripts/metricas.redis`.

### Resultado observado

| Métrica | Antes | Después | Diferencia |
|---|---|---|---|
| `keyspace_hits` | 18 | 26 | **+8** |
| `keyspace_misses` | 5 | 9 | **+4** |
| `expired_keys` | 4 | 4 | 0 |
| `evicted_keys` | 0 | 0 | 0 |

**Tasa de hit de la prueba:**

```
8 / (8 + 4) x 100 = 66,67 %
```

El resultado coincide exactamente con la secuencia diseñada, lo que confirma
que las 12 lecturas se contabilizaron como se esperaba y que no hubo lecturas
ajenas mezcladas en la medición.

### Interpretación

- **Los 8 hits** son lecturas que se resolvieron en memoria sin tocar la
  fuente de verdad: es el ahorro que justifica el módulo.
- **Los 4 misses** no son un fallo. Son el camino normal la primera vez que se
  pide una ficha: la aplicación va a la fuente de verdad, responde y deja la
  copia. Un sistema con 0 % de miss sería uno donde nada se pide por primera
  vez.
- **El 66,67 % no es la tasa de la plataforma**, es la de esta secuencia
  concreta, que se diseñó con esa proporción para poder verificarla. La tasa
  real dependería del tráfico y de la relación entre lecturas repetidas y
  fichas nuevas.
- **`evicted_keys` en 0** confirma que 256 MB sobran para este volumen: no
  hubo presión de memoria, así que la política de evicción no llegó a
  actuar. Se verificó que está configurada (`03_memoria.png`), no que se
  haya disparado.
- **`expired_keys` en 4** antes de la prueba y sin cambios durante ella: las
  claves de la secuencia tenían TTL de 300 s y la medición duró mucho menos.
  Los 4 vencimientos previos corresponden a la sesión de prueba y a las
  cachés de 60 s de los pasos anteriores, y son la evidencia de que la
  expiración la maneja el servidor y no un proceso de la aplicación.

## 4. Limitaciones del laboratorio

- **Nodo único.** No se prueba failover, distribución de claves ni
  consistencia entre réplicas. La comparación con primary + réplicas y con
  Redis Cluster está en `docs/memoria_y_escalabilidad.md`.
- **Ejecución secuencial desde `redis-cli`.** La medición refleja el
  comportamiento de los contadores, no la concurrencia real de miles de
  clientes simultáneos. La atomicidad de `INCR`, `HINCRBY`, `ZINCRBY` y
  `MULTI`/`EXEC` se demuestra por el diseño y por las respuestas observadas,
  no por una prueba de carga concurrente.
- **La tasa de hit depende de la secuencia ejecutada**, que fue elegida para
  ser verificable. No representa el tráfico real de la plataforma.
- **No se forzó una evicción.** Llenar 256 MB requeriría cargar cientos de
  miles de claves, lo que excede el alcance del hito. La política quedó
  configurada y justificada documentalmente, que es lo que pide RF10.

## 5. Conclusión

El módulo se comportó como se diseñó:

- Las sesiones vencen solas por inactividad y se renuevan únicamente con un
  `EXPIRE` explícito, como demuestra la diferencia entre `05_sesion_ttl.png`
  (el TTL que no se reinicia con `HSET`) y `06_sesion_renovada.png`.
- El ciclo Cache-Aside completo —miss, carga, hit e invalidación— quedó
  registrado en una sola secuencia.
- Las operaciones concurrentes devolvieron los valores exactos esperados
  (4552 en el contador, Top 3 del ranking), sin ningún incremento perdido.
- La medición de hits y misses coincidió con la secuencia diseñada.

Lo que cambiaría para sostener el tráfico real del torneo no es el modelo de
claves sino la topología: réplicas de lectura primero, porque el patrón
dominante es lectura de sesión y de ficha.
