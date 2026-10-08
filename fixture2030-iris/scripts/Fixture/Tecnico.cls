/// Director tecnico. Hereda Nombre y Nacionalidad de Persona.
Class Fixture.Tecnico Extends Fixture.Persona
{

/// Seleccion que dirige (codigo FIFA). Puede no coincidir con su Nacionalidad.
Property Seleccion As %String(MAXLEN = 3, PATTERN = "3U") [ Required ];

}
