/// Partido del Fixture 2030. Es una maquina de estados:
///   Pendiente -> EnJuego -> Finalizado   (no se puede retroceder ni saltear pasos)
/// Es el padre de sus Eventos (relacion padre-hijo): si se borra el partido,
/// se borran sus eventos; un evento no puede existir sin su partido.
Class Fixture.Partido Extends %Persistent
{

/// Codigo de negocio del partido (ej. "M001"). Unico.
Property Codigo As %String(MAXLEN = 10) [ Required ];

Property Sede As %String(MAXLEN = 60) [ Required ];

Property Fecha As %TimeStamp;

/// Codigos FIFA de las selecciones (mismos _id que en el modulo documental).
Property Local As %String(MAXLEN = 3, PATTERN = "3U");

Property Visitante As %String(MAXLEN = 3, PATTERN = "3U");

/// Estado actual. Un partido nuevo nace siempre Pendiente.
Property Estado As %String(VALUELIST = ",Pendiente,EnJuego,Finalizado") [ InitialExpression = "Pendiente", Required ];

/// Composicion: los eventos pertenecen al partido y se guardan dentro de el.
Relationship Eventos As Fixture.Evento [ Cardinality = children, Inverse = Partido ];

/// Arbitro principal. Asociacion uno-a-muchos (un arbitro dirige muchos partidos).
Relationship Arbitro As Fixture.Arbitro [ Cardinality = one, Inverse = Partidos ];

/// No puede haber dos partidos con el mismo codigo.
Index CodigoIdx On Codigo [ Unique ];

/// Indice del lado "muchos": evita recorrer todos los partidos para saber
/// cuales dirige un arbitro (Swizzling de Arbitro.Partidos y control al borrar).
Index ArbitroIdx On Arbitro;

/// Reglas de la maquina de estados. Devuelve 1 si se puede pasar de pDesde a pHacia.
ClassMethod TransicionValida(pDesde As %String, pHacia As %String) As %Boolean
{
    Quit:(pDesde = pHacia) 1
    Quit:((pDesde = "Pendiente") && (pHacia = "EnJuego")) 1
    Quit:((pDesde = "EnJuego") && (pHacia = "Finalizado")) 1
    Quit 0
}

/// Operacion encapsulada para avanzar el estado del partido y guardarlo.
/// Uso: Set sc = partido.CambiarEstado("EnJuego")
Method CambiarEstado(pNuevo As %String) As %Status
{
    If '..TransicionValida(..Estado, pNuevo) {
        Quit $$$ERROR($$$GeneralError, "Transicion ilegal de estado: "_..Estado_" -> "_pNuevo)
    }
    Set ..Estado = pNuevo
    Quit ..%Save()
}

/// Se ejecuta antes de cada guardado. Es la ultima barrera: aunque alguien haga
/// "Set p.Estado = ..." directamente sin pasar por CambiarEstado, el guardado se rechaza.
Method %OnBeforeSave(insert As %Boolean) As %Status [ Private, ServerOnly = 1 ]
{
    // 1. Un partido nuevo nace Pendiente
    If insert && (..Estado '= "Pendiente") {
        Quit $$$ERROR($$$GeneralError, "Un partido nuevo debe crearse en estado Pendiente (vino "_..Estado_")")
    }
    // 2. Si ya existia, se compara contra el estado guardado en disco
    If 'insert {
        Set tAnterior = ..EstadoGetStored(..%Id())
        If '..TransicionValida(tAnterior, ..Estado) {
            Quit $$$ERROR($$$GeneralError, "Transicion ilegal de estado: "_tAnterior_" -> "_..Estado)
        }
    }
    // 3. Solo un arbitro con rol Principal puede dirigir el partido
    If $IsObject(..Arbitro) && (..Arbitro.Rol '= "Principal") {
        Quit $$$ERROR($$$GeneralError, "El arbitro asignado al partido debe tener rol Principal (tiene "_..Arbitro.Rol_")")
    }
    Quit $$$OK
}

}
