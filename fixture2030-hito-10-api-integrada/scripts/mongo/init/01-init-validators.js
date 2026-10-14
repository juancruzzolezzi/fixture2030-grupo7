// Se ejecuta UNA sola vez, automáticamente, la primera vez que arranca el
// contenedor con el volumen de datos vacío (mecanismo estándar de la imagen
// oficial de Mongo: todo archivo .js en /docker-entrypoint-initdb.d se corre
// con mongosh contra la base indicada en MONGO_INITDB_DATABASE).
//
// Acá NO se cargan datos (eso lo hace seed/generate_and_load.py, que corre
// desde afuera con pymongo). Acá solo se crean las colecciones con su
// validación documental (RF7), para que la carga y cualquier inserción
// posterior pasen por la misma regla, la usen desde donde la usen.

db = db.getSiblingDB(process.env.MONGO_INITDB_DATABASE || "fixture2030");

// ---------------------------------------------------------------------------
// equipos
// ---------------------------------------------------------------------------
db.createCollection("equipos", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["_id", "nombre", "confederacion", "sede_mundial", "ranking_fifa"],
      properties: {
        _id: {
          bsonType: "string",
          pattern: "^[A-Z]{3}$",
          description: "código de 3 letras del equipo (identificador de negocio, ver documento de decisiones)",
        },
        nombre: { bsonType: "string", minLength: 2 },
        confederacion: {
          enum: ["CONMEBOL", "UEFA", "CAF", "AFC", "CONCACAF", "OFC"],
        },
        sede_mundial: { bsonType: "bool" },
        ranking_fifa: { bsonType: "int", minimum: 1, maximum: 210 },
        entrenador: {
          bsonType: "object",
          properties: { nombre: { bsonType: "string" } },
        },
        cantidad_jugadores: { bsonType: ["int", "null"], minimum: 0 },
      },
    },
  },
  validationLevel: "strict",
  validationAction: "error",
});

// ---------------------------------------------------------------------------
// jugadores
// ---------------------------------------------------------------------------
db.createCollection("jugadores", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["_id", "equipo_id", "nombre", "apellido", "dorsal", "posicion"],
      properties: {
        _id: {
          bsonType: "string",
          pattern: "^[A-Z]{3}-[0-9]{2}$",
          description: "código de equipo + dorsal (ver estrategia de identificadores)",
        },
        equipo_id: { bsonType: "string", pattern: "^[A-Z]{3}$" },
        equipo_resumen: {
          bsonType: "object",
          properties: {
            nombre: { bsonType: "string" },
            confederacion: { bsonType: "string" },
          },
        },
        nombre: { bsonType: "string", minLength: 1 },
        apellido: { bsonType: "string", minLength: 1 },
        dorsal: { bsonType: "int", minimum: 1, maximum: 99 },
        posicion: { enum: ["Arquero", "Defensor", "Mediocampista", "Delantero"] },
        fecha_nacimiento: { bsonType: "string" },
        altura_cm: { bsonType: "int", minimum: 140, maximum: 220 },
        pie_habil: { enum: ["Derecho", "Izquierdo", "Ambidiestro"] },
        estadisticas: {
          bsonType: "object",
          properties: {
            partidos_jugados: { bsonType: "int", minimum: 0 },
            goles: { bsonType: "int", minimum: 0 },
            asistencias: { bsonType: "int", minimum: 0 },
            tarjetas_amarillas: { bsonType: "int", minimum: 0 },
            tarjetas_rojas: { bsonType: "int", minimum: 0 },
          },
        },
      },
    },
  },
  validationLevel: "strict",
  validationAction: "error",
});

print("Colecciones 'equipos' y 'jugadores' creadas con validación $jsonSchema.");
