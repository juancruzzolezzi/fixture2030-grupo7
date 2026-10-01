# Fixture 2030 — Módulo de Caché de Usuarios y Sesiones (Hito 7, Redis)

Grupo 7 — Ingeniería de Datos II

Módulo clave/valor para sesiones de usuario y caché de lecturas frecuentes del
Fixture 2030. No reemplaza a los módulos anteriores: administra el estado
transitorio y las copias de acceso rápido, con la fuente de verdad siempre
fuera de Redis.

## Requisitos

- Docker Desktop (o Docker Engine + Compose) corriendo.
- Puerto 6379 libre.

No hace falta instalar ningún cliente: `redis-cli` viene dentro de la imagen
oficial.

## Estructura

```
fixture2030-redis/
├── docker-compose.yml
├── .env.example                Ruta de persistencia (necesario en Windows)
├── scripts/
│   ├── inicializacion.redis    Verificación del servidor y política de memoria
│   ├── carga_muestra.redis     Conjunto de datos reproducible
│   ├── sesiones.redis          Ciclo de vida completo de una sesión
│   ├── cache.redis             Cache-Aside: hit, miss e invalidación
│   ├── concurrencia.redis      Operaciones atómicas y MULTI/EXEC
│   └── metricas.redis          Medición, INFO y SCAN
├── docs/
│   ├── patrones_de_acceso.md
│   ├── modelo_clave_valor.md
│   ├── ciclo_de_vida_e_invalidacion.md
│   ├── memoria_y_escalabilidad.md
│   └── evidencia/
└── README.md
```

## 1. Preparar la persistencia

El `docker-compose.yml` monta los datos en `${HOME}/docker/data/redis` (RNF2).

**En Windows** hay que definir esa variable, porque el sistema no la trae.
Copiar `.env.example` como `.env` y completar la ruta:

```powershell
Copy-Item .env.example .env
echo $env:USERPROFILE     # para saber qué ruta poner adentro
```

Dentro de `.env`, por ejemplo: `HOME=C:/Users/juanc`

**En Linux o macOS** no hace falta: `HOME` ya existe.

## 2. Levantar el ambiente

```bash
docker compose up -d
docker compose ps
docker compose logs -f redis     # salir con Ctrl+C
```

La primera vez, Compose descarga `redis:latest`. Para actualizar la imagen
antes de una nueva corrida: `docker compose pull redis` y luego
`docker compose up -d`.

## 3. Abrir el cliente y verificar

```bash
docker exec -it fixture2030-redis redis-cli
```

Ya dentro de `redis-cli`:

```
PING          -> PONG
INFO server   -> anotar redis_version para la evidencia
```

## 4. Ejecutar los scripts

Los archivos de `scripts/` están comentados con `--` para poder leerlos. Ese
no es un comentario que Redis entienda: **los scripts se ejecutan copiando y
pegando los bloques de comandos dentro de `redis-cli`**, igual que la demo de
la clase. Conviene ir bloque por bloque y mirar la respuesta de cada comando
antes de seguir.

Orden recomendado:

| # | Archivo | Qué demuestra |
|---|---|---|
| 1 | `inicializacion.redis` | El servidor responde y queda configurado el límite de memoria |
| 2 | `carga_muestra.redis` | Los datos de prueba, con las cinco estructuras |
| 3 | `sesiones.redis` | Crear, leer, renovar, expirar y cerrar una sesión |
| 4 | `cache.redis` | Cache hit, cache miss e invalidación |
| 5 | `concurrencia.redis` | Contadores atómicos, ranking y `MULTI`/`EXEC` |
| 6 | `metricas.redis` | Medición de hits/misses, memoria e inspección con `SCAN` |

Los scripts también quedan montados dentro del contenedor en `/scripts`, tal
como los expone el `docker-compose.yml`.

### Dos bloques necesitan esperar

- `sesiones.redis`, bloque 3 y bloque 5: hay que dejar pasar los segundos que
  indica el comentario. Si se pegan los comandos de corrido, los `TTL`
  devuelven el mismo número y la demostración no muestra nada.
- `metricas.redis`, bloque 5: lo mismo, para que la clave alcance a vencer.

## 5. Medición (RF12)

El método está en `scripts/metricas.redis`: se anotan `keyspace_hits` y
`keyspace_misses` de `INFO stats`, se ejecuta una secuencia conocida de
lecturas (8 con la clave presente y 4 con la clave ausente), se vuelve a leer
`INFO stats` y se calcula:

```
tasa_de_hit = hits / (hits + misses) x 100
```

Los valores observados se registran en `docs/evidencia/`, junto con la fecha
de ejecución, la versión que reporte `INFO server` y los recursos de la
notebook (RNF10).

## 6. Detener y reiniciar sin perder datos

| Acción | Comando | ¿Se pierden los datos? |
|---|---|---|
| Parar | `docker compose stop` | No |
| Volver a levantar | `docker compose start` | No |
| Parar y sacar el contenedor | `docker compose down` | No: el directorio montado queda |
| Empezar de cero | `docker compose down` y borrar a mano `~/docker/data/redis` | Sí, sólo con esa intención explícita |

## Notas del ambiente

**Un solo nodo.** Este laboratorio corre una única instancia. Sirve para
entender el modelado, las operaciones y el ciclo de vida, pero no demuestra
tolerancia a fallas ni distribución de claves. La comparación con
primary + réplicas y con Redis Cluster está en
`docs/memoria_y_escalabilidad.md`.

**Uso de `latest`.** La imagen no está fijada a una versión. Este módulo se
probó el **30/09/2026** contra **Redis 8.10.2** (versión reportada por
`INFO server`). Si al reconstruir el ambiente `docker compose up -d` descarga
una versión distinta y algo cambia de comportamiento, registrarlo acá.

**Seguridad local (RNF7).** No hay tokens reales, contraseñas ni credenciales
en los scripts ni en la documentación. El token de sesión se modela como un
campo dentro del Hash y nunca como parte del nombre de la clave, porque las
claves aparecen en logs, capturas y salidas de `SCAN`.

**Inspección (RNF8).** El módulo usa `SCAN` con cursor y `MATCH`. No se usa
`KEYS *`, que recorre todo el keyspace antes de responder y bloquea el
servidor mientras lo hace.
