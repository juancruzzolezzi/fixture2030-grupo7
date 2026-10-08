/// Clase base persistente del dominio. Jugador, Arbitro y Tecnico heredan de ella
/// y comparten su extent: un SELECT sobre la tabla Fixture.Persona devuelve a los tres.
/// La herencia modela tipos que no cambian (un jugador no "se vuelve" arbitro);
/// los estados variables (lesionado, suspendido) serian propiedades, no subclases.
Class Fixture.Persona Extends %Persistent
{

/// Nombre completo.
Property Nombre As %String(MAXLEN = 100) [ Required ];

/// Codigo FIFA de 3 letras mayusculas (ej. "ARG"), el mismo que usa el modulo documental.
Property Nacionalidad As %String(MAXLEN = 3, PATTERN = "3U") [ Required ];

Property FechaNacimiento As %Date;

/// Soporta la consulta por nacionalidad (WHERE Nacionalidad = 'ARG').
Index NacionalidadIdx On Nacionalidad;

}
