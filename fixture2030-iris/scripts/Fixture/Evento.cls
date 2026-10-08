/// Evento de un partido (gol, tarjeta, sustitucion). Es hijo de Partido:
/// su ID tiene la forma "idPartido||n" y se guarda fisicamente dentro del partido.
/// Los eventos son inalterables: una vez registrados no se modifican.
Class Fixture.Evento Extends %Persistent
{

Property Tipo As %String(VALUELIST = ",Gol,Amarilla,Roja,Sustitucion") [ Required ];

/// Minuto de juego. El 0 no existe (el partido arranca en el minuto 1);
/// 130 cubre alargue y descuento.
Property Minuto As %Integer(MINVAL = 1, MAXVAL = 130) [ Required ];

/// Lado hijo de la composicion con Partido (obligatorio por definicion).
Relationship Partido As Fixture.Partido [ Cardinality = parent, Inverse = Eventos ];

/// Jugador que protagoniza el evento (opcional). Lado "muchos" de la relacion
/// uno-a-muchos con Jugador. Por defecto, IRIS no deja borrar un jugador
/// que todavia tenga eventos apuntandolo.
Relationship Jugador As Fixture.Jugador [ Cardinality = one, Inverse = Eventos ];

/// Indice del lado "muchos": para cargar Jugador.Eventos, IRIS busca que eventos
/// apuntan a ese jugador. Sin indice seria un recorrido completo de todos los eventos.
Index JugadorIdx On Jugador;

Method %OnBeforeSave(insert As %Boolean) As %Status [ Private, ServerOnly = 1 ]
{
    // 1. Inalterabilidad: un evento ya guardado no se puede modificar
    If 'insert {
        Quit $$$ERROR($$$GeneralError, "Los eventos son inalterables: el evento "_..%Id()_" ya fue registrado")
    }
    // 2. Un partido Finalizado no admite eventos nuevos
    If $IsObject(..Partido) && (..Partido.Estado = "Finalizado") {
        Quit $$$ERROR($$$GeneralError, "El partido "_..Partido.Codigo_" esta Finalizado: no admite eventos nuevos")
    }
    Quit $$$OK
}

}
