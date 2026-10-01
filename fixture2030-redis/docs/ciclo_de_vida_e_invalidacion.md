# Ciclo de vida e invalidación — Hito 7 (Redis) — Fixture 2030

## 1. Ciclo de vida de una sesión

### Regla temporal

Una sesión es válida mientras **exista la clave**. No hay un campo que la
aplicación tenga que interpretar: si `HGET` devuelve vacío, no hay sesión.
Esto evita el error de leer `ultimo_acceso` y calcular en la aplicación si
venció, que dejaría sesiones "muertas" ocupando memoria hasta que alguien las
revisara.

| Etapa | Qué pasa | Comandos |
|---|---|---|
| **Creación** | Al autenticarse se escribe el Hash y se le asigna la ventana de inactividad. | `HSET` + `EXPIRE 1800` |
| **Validación** | Cada request lee un solo campo. | `HGET … estado` |
| **Renovación** | Una petición válida registra la actividad y **reinicia** la ventana. | `MULTI` → `HSET` + `HINCRBY` + `EXPIRE 1800` → `EXEC` |
| **Expiración** | Sin actividad por 30 min, el servidor borra la clave solo. | (automático) |
| **Cierre explícito** | El logout no espera al TTL. | `DEL` |

### Por qué 30 minutos

Es el equilibrio entre dos costos concretos:

- **Más corto** (por ejemplo 5 min): un usuario que mira un partido sin tocar
  la pantalla tendría que volver a autenticarse en medio del entretiempo.
- **Más largo** (por ejemplo 8 h): una sesión abierta en una computadora
  compartida queda usable mucho después de que la persona se fue, y la
  memoria se llena de sesiones que nadie está usando.

30 minutos cubre la duración de un tiempo de juego más el entretiempo con
actividad normal, y limita la ventana de riesgo si alguien deja la sesión
abierta.

### El evento que renueva es explícito

Éste es el punto que más fácil se hace mal. **Actualizar un campo del Hash no
extiende la vida de la clave.** Si la aplicación sólo hiciera
`HSET ultimo_acceso`, la sesión de un usuario activo se cerraría igual a los
30 minutos de haberse creado.

Por eso la renovación es una decisión aparte (`EXPIRE`), y va junto con el
registro de actividad dentro de `MULTI`/`EXEC`: registrar la actividad y
renovar la ventana tienen que ocurrir las dos o ninguna.

El bloque 3 de `scripts/sesiones.redis` demuestra el problema: tras esperar
10 segundos y hacer `HSET`, el `TTL` sigue en ~50 y no volvió a 60.

### Comportamiento ante una sesión inexistente

Redis no devuelve error: devuelve vacío, y `TTL` devuelve `-2`. La aplicación
interpreta esa respuesta como "no hay sesión" y manda a autenticarse de nuevo.

Es deliberadamente **el mismo resultado** para los tres casos —vencida por
inactividad, cerrada con logout, o que nunca existió— porque desde el punto de
vista de la autorización los tres significan lo mismo, y distinguirlos daría
información innecesaria a quien esté probando sesiones ajenas.

### Cómo se comprueba que venció

| Respuesta de `TTL` | Significado |
|---|---|
| 0 o positivo | Segundos que le quedan |
| `-1` | La clave existe pero **no tiene expiración** (no debería pasar con una sesión) |
| `-2` | La clave ya no existe |

Un `-1` sobre una clave de sesión sería un defecto: significaría que alguien
la creó sin `EXPIRE` o le aplicó `PERSIST`, y esa sesión no vencería nunca.

## 2. Caché: Cache-Aside sobre la ficha de partido

### Qué se acelera y cuál es su fuente de verdad

El dato elegido es la **ficha de un partido** (equipos, fecha, estado,
marcador): es lo que más se lee durante la jornada y es idéntico para todos
los usuarios que lo piden.

Su **fuente de verdad son los módulos de los hitos anteriores**, no Redis. La
copia que vive en `fixture2030:cache:partido:<id>` es descartable por
definición y se puede reconstruir en cualquier momento.

### Los dos caminos

**Cache hit** — `GET` devuelve el valor: la aplicación responde desde memoria
y no toca la fuente de verdad.

**Cache miss** — `GET` devuelve vacío. Un miss **no es un error**, es el
camino normal la primera vez:

1. `GET` devuelve vacío.
2. La aplicación consulta la fuente de verdad.
3. Responde al usuario con ese dato.
4. Deja una copia con `SETEX … 60`.

### Invalidación cuando cambia la fuente de verdad

Cuando se registra un gol, la aplicación actualiza la fuente de verdad y,
**como parte del mismo flujo**, ejecuta `DEL` sobre la clave de caché.

Se eligió **borrar en vez de reescribir**: si la escritura de la caché
fallara, el peor caso de un `DEL` es un miss —que se resuelve solo leyendo la
fuente— mientras que una reescritura fallida podría dejar servido un marcador
viejo. Ante la duda, el camino que degrada a "más lento" es mejor que el que
degrada a "incorrecto".

### Por qué el TTL solo no alcanza

Si el gol se registrara sin ejecutar el `DEL`, los usuarios seguirían viendo
el marcador anterior hasta que venciera el TTL: hasta **60 segundos de
marcador equivocado** durante un partido en vivo.

El TTL es el **límite máximo** de vida de una copia, no una estrategia de
coherencia. Es la red de seguridad para el caso en que la invalidación se
pierda por un error; la coherencia la da la invalidación explícita.

### Por qué 60 segundos

Es el tiempo máximo que se acepta servir una ficha sin volver a la fuente.
Corto, porque durante un partido en vivo el marcador cambia y una copia vieja
se nota enseguida. Si el dato fuera estático (el fixture de la fase de grupos,
por ejemplo) el TTL podría ser de horas.

### Si Redis no tiene la clave o no está disponible

Todo lo que vive bajo `fixture2030:cache:` es reconstruible:

- **Clave ausente** → el flujo del cache miss. Funciona igual, con más
  latencia.
- **Redis entero caído** → la plataforma sigue respondiendo contra la fuente
  de verdad, con más latencia y más carga. **No se pierde ningún dato de
  negocio**, porque ninguna ficha nace en Redis.
- Lo que sí se pierde son las sesiones: los usuarios vuelven a autenticarse.
  Es una molestia aceptable y no una pérdida de información del torneo.
