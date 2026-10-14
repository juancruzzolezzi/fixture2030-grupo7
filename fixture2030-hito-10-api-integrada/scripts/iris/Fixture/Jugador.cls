/// Jugador de una seleccion. Hereda Nombre y Nacionalidad de Persona.
Class Fixture.Jugador Extends Fixture.Persona
{

/// Dorsal. Entero estricto entre 1 y 99.
Property Numero As %Integer(MINVAL = 1, MAXVAL = 99) [ Required ];

/// Solo se aceptan estos cuatro valores.
Property Posicion As %String(VALUELIST = ",Arquero,Defensor,Mediocampista,Delantero") [ Required ];

/// Eventos que protagonizo (goles, tarjetas). Lado "uno" de la relacion uno-a-muchos
/// con Evento; el indice esta del lado "muchos" (Evento.JugadorIdx).
Relationship Eventos As Fixture.Evento [ Cardinality = many, Inverse = Jugador ];

}
