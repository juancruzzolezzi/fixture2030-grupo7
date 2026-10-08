/// Arbitro del torneo. Hereda Nombre y Nacionalidad de Persona.
Class Fixture.Arbitro Extends Fixture.Persona
{

/// Funcion que cumple en la terna arbitral.
Property Rol As %String(VALUELIST = ",Principal,Asistente,VAR") [ Required ];

/// Partidos que dirige como principal. Lado "uno" de la relacion con Partido;
/// el indice esta del lado "muchos" (Partido.ArbitroIdx).
Relationship Partidos As Fixture.Partido [ Cardinality = many, Inverse = Arbitro ];

}
