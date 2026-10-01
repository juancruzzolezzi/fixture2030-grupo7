# Modelo clave/valor — Hito 7 (Redis) — Fixture 2030

## 1. Nomenclatura de claves

Todas las claves siguen esta convención:

```
fixture2030:<dominio>:<identificador>[:<subrecurso>]
```

| Parte | Para qué está |
|---|---|
| `fixture2030` | Prefijo del sistema. Permite reconocer y aislar las claves de este TPO si la instancia se compartiera. |
| `<dominio>` | Qué tipo de cosa es: `sesion`, `cache`, `contador`, `encuesta`, `conectados`, `actividad`. |
| `<identificador>` | El id estable que la aplicación ya tiene en la mano (`user-00001`, `F2030-006`). |
| `<subrecurso>` | Sólo cuando hace falta distinguir dentro de la misma entidad (`:visitas`, `:figura`). |

Reglas que se siguen:

- **Identificadores estables.** Se usa `F2030-006`, nunca el nombre del
  partido: si cambiara la descripción, la clave seguiría siendo válida.
- **Alcance explícito.** `fixture2030:contador:partido:F2030-006:visitas` es el
  contador *de ese partido*, no uno global. El TTL y las operaciones son
  coherentes con ese alcance.
- **Ningún secreto en el nombre.** El token de sesión es un campo dentro del
  Hash, nunca parte de la clave: la clave aparece en logs, capturas y salidas
  de `SCAN`.
- **Los `:` son convención humana.** Redis no crea carpetas; el separador
  existe para que la clave sea legible y filtrable con `SCAN MATCH`.

## 2. Claves, estructuras y el patrón que las justifica

| Clave | Estructura | Patrón | TTL | Por qué esa estructura |
|---|---|---|---|---|
| `fixture2030:sesion:<usuario_id>` | Hash | P1, P2 | 1800 s | La sesión tiene varios atributos que se leen y actualizan por separado. Con un Hash se lee sólo `estado` en la validación, sin traer ni parsear todo el objeto, y se incrementa `paginas_vistas` dentro del servidor. |
| `fixture2030:cache:partido:<partido_id>` | String | P3, P4 | 60 s | La respuesta ya viene serializada de la fuente de verdad y se devuelve entera. No hace falta acceder a campos sueltos, así que un String alcanza. |
| `fixture2030:contador:partido:<id>:visitas` | String (entero) | P5 | 86400 s | `INCR` opera el entero dentro del servidor. Es la operación atómica que evita el ciclo leer-sumar-escribir. |
| `fixture2030:encuesta:<partido_id>:figura` | Sorted Set | P6 | 86400 s | Se necesita el Top N ordenado por votos. El Sorted Set mantiene el orden por score y `ZREVRANGE` devuelve el ranking sin ordenar nada en la aplicación. |
| `fixture2030:conectados:partido:<id>` | Set | P7 | 3600 s | Sólo interesa pertenencia, sin orden y sin repetidos. Si un usuario abre dos pestañas, `SADD` no lo duplica. |
| `fixture2030:actividad:<usuario_id>` | List | P8 | 1800 s | Secuencia por orden de llegada. `LPUSH` deja lo más nuevo primero y `LTRIM` acota la lista a 10 elementos para que no crezca sin límite. |

Cada estructura del modelo tiene al menos una operación concreta que la usa;
no hay ninguna clave incluida "por completitud".

## 3. Atributos de la sesión

| Campo | Para qué |
|---|---|
| `usuario_id` | Identifica al dueño de la sesión. |
| `rol` | Decide qué puede hacer (`fan`, `moderador`). |
| `estado` | Marca de acceso: es el único campo que lee la validación de cada request. |
| `ultimo_acceso` | Momento de la última actividad válida. Sirve para auditar; **no** es lo que hace vencer la sesión. |
| `paginas_vistas` | Actividad acumulada, incrementada con `HINCRBY`. |

El **token no se usa como nombre de clave**. La clave sirve para localizar; el
token es dato sensible y no debe aparecer en una salida de `SCAN` ni en una
captura de pantalla.

## 4. Concurrencia

### El antipatrón que se evita

Si la aplicación hiciera `GET` del contador, sumara en su código y luego
`SET`, dos clientes simultáneos podrían leer el mismo valor y pisarse el
incremento. El problema no es Redis: es que leer, calcular y escribir son tres
operaciones separadas y otro cliente puede meterse en el medio.

La solución es no sacar el dato del servidor para modificarlo.

### Operaciones atómicas usadas

| Operación | Comando | Qué garantiza |
|---|---|---|
| Sumar una visita | `INCR` | Un solo comando. Dos visitas simultáneas dan +2, nunca +1. |
| Sumar actividad a la sesión | `HINCRBY` | Modifica el campo dentro del servidor, sin traer el Hash. |
| Sumar un voto | `ZINCRBY` | Suma y reordena el ranking en la misma operación. |
| Marcar conectado | `SADD` | Idempotente por definición: el mismo miembro no entra dos veces. |

### Cuando hace falta una secuencia

Un voto real no es sólo el `ZINCRBY`: también cuenta como actividad del
usuario y debe renovar su sesión. Son cuatro comandos que no pueden quedar a
medio aplicar. Se agrupan en `MULTI` / `EXEC`, que encola y ejecuta el bloque
sin que otro cliente se intercale.

Con el alcance que tiene:

- `MULTI`/`EXEC` **evita la intercalación**, que es el riesgo real acá.
- **No es una transacción con rollback.** Si un comando estuviera mal formado,
  Redis no deshace lo ya aplicado. El diseño tiene que preverlo, y por eso la
  secuencia sólo agrupa operaciones que ya se validaron antes de encolarlas.

La demostración está en `scripts/concurrencia.redis`.
