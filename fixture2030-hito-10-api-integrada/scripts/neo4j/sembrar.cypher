// Datos de prueba minimos para el Hito 10 (API integrada). Usa los mismos
// codigos F2030-xxx del Hito 5, no es un reemplazo de esa carga completa.
//
// Cada sentencia busca sus nodos por clave de negocio (MATCH/MERGE con el
// patron completo), en vez de reusar una variable de una sentencia anterior:
// cypher-shell ejecuta cada linea terminada en ';' como una transaccion
// independiente, asi que una variable como 'p' de una sentencia previa NO
// sigue apuntando al mismo nodo en la siguiente.
MERGE (arg:Equipo {codigo: 'ARG'}) SET arg.nombre = 'Argentina', arg.confederacion = 'CONMEBOL', arg.esAnfitrion = true;
MERGE (esp:Equipo {codigo: 'ESP'}) SET esp.nombre = 'España', esp.confederacion = 'UEFA', esp.esAnfitrion = true;

MERGE (bue:Sede {codigo: 'BUE'}) SET bue.nombre = 'Estadio Monumental', bue.ciudad = 'Buenos Aires', bue.pais = 'Argentina';

MERGE (j1:Jugador {codigo: 'ARG-10'}) SET j1.nombre = 'Mateo', j1.apellido = 'Gonzalez', j1.dorsal = 10, j1.posicion = 'Delantero';
MATCH (j1:Jugador {codigo: 'ARG-10'}), (arg:Equipo {codigo: 'ARG'}) MERGE (j1)-[:PERTENECE_A]->(arg);

MERGE (p:Partido {codigo: 'F2030-006'}) SET p.fecha = date('2030-06-18'), p.fase = 'Fase de grupos';
MATCH (p:Partido {codigo: 'F2030-006'}), (bue:Sede {codigo: 'BUE'}) MERGE (p)-[:SE_JUEGA_EN]->(bue);
MATCH (arg:Equipo {codigo: 'ARG'}), (p:Partido {codigo: 'F2030-006'}) MERGE (arg)-[ra:DISPUTA]->(p) SET ra.condicion = 'A';
MATCH (esp:Equipo {codigo: 'ESP'}), (p:Partido {codigo: 'F2030-006'}) MERGE (esp)-[rb:DISPUTA]->(p) SET rb.condicion = 'B';

MERGE (ev:Evento {codigo: 'EVT-F2030-006-01'}) SET ev.tipo = 'Gol', ev.minuto = 23;
MATCH (ev:Evento {codigo: 'EVT-F2030-006-01'}), (p:Partido {codigo: 'F2030-006'}) MERGE (ev)-[:OCURRE_EN]->(p);
MATCH (j1:Jugador {codigo: 'ARG-10'}), (ev:Evento {codigo: 'EVT-F2030-006-01'}) MERGE (j1)-[:PROTAGONIZA]->(ev);
