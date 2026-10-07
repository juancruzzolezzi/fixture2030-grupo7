# Retención y granularidad

Las estadísticas en vivo no valen lo mismo durante el partido, durante el torneo y años después. La política define qué se conserva con precisión original, qué se resume y qué expira.

## 1. Ciclo de vida

| Etapa | Granularidad | Uso | Consulta típica |
|---|---|---|---|
| Captura | 1 s (crudo) | Pantalla en vivo, comparación en ventanas cortas | PA1, PA2, PA3, PA5 |
| Durante el torneo | 1 s (crudo) | Análisis de cada partido y comparaciones entre partidos | PA4, PA7, PA9, PA10 |
| Después del torneo | Ventanas de 1 y 5 minutos | Histórico, estadísticas de la edición 2030 | Resúmenes por ventana (AG2) |
| Eventos | Sin resumir | Se conservan siempre: son pocos y no se pueden recalcular | PA6, PA9 |

## 2. Política propuesta

| Dato | Se conserva crudo | Luego |
|---|---|---|
| `estadisticas` | Hasta 15 días después de la final (≈ 50 días) | Se resume en ventanas de 1 minuto: AVG de posesión, MAX de pases y tiros |
| `audiencia` | Hasta 15 días después de la final | Se resume en ventanas de 1 minuto: MAX, MIN y AVG de usuarios por región |
| `eventos` | Indefinidamente | No se resume |

**Por qué estos plazos:** el torneo dura ≈ 33 días; mantener los datos crudos hasta dos semanas después de la final permite revisar cualquier partido segundo a segundo mientras el torneo tiene interés operativo. Después, la pregunta de negocio pasa a ser la tendencia, no cada segundo.

**Agregación según semántica** (la misma de `modelo_multidimensional.md`): posesión → AVG; contadores → MAX por ventana; usuarios → MAX/MIN/AVG; eventos → COUNT.

## 3. Cómo se aplica en InfluxDB 3 Core

En Core el período de retención se fija **al crear la base** y no se puede cambiar después. Por eso el diseño usa dos bases:

| Base | Contenido | Retención |
|---|---|---|
| `fixture2030_series` | Datos crudos de las tres tablas | ≈ 50 días |
| `fixture2030_series_historico` | Resúmenes por ventana + eventos | Sin vencimiento |

Los resúmenes se obtienen con consultas de ventana como AG2: la misma consulta de agregación acotada a cada rango de tiempo (`WHERE time >= inicio AND time < fin`). En la prueba se ve la reducción: 6.300 puntos de un equipo en un partido pasan a 21 filas de 5 minutos (serían 105 filas con ventanas de 1 minuto).

**En la prueba local** la base se crea sin retención, porque los datos son simulados y se necesitan para repetir las consultas. La política queda definida y justificada pero no aplicada al laboratorio (el hito pide definirla y documentarla, RF10).

## 4. Efecto de la política

| Aspecto | Efecto |
|---|---|
| Consultas en vivo | Sin cambios: siempre leen datos crudos recientes |
| Análisis histórico | Se responde con resúmenes; ya no se puede ver un segundo puntual de un partido viejo |
| Almacenamiento | Las ventanas de 1 minuto reducen 60 veces los puntos de estadísticas y audiencia (≈ 11,2M → ≈ 187.000) |
| Costo | El almacenamiento deja de crecer con cada torneo al ritmo de los datos crudos |
