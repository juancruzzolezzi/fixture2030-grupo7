/// Demostracion completa del Hito 9, ejecutable desde el Terminal de IRIS:
///   Do ##class(Fixture.Demo).Ejecutar()
/// Cada seccion es un metodo aparte: asi cada una abre los objetos frescos desde
/// disco y un objeto que quedo "sucio" en memoria por un rechazo no contamina la siguiente.
Class Fixture.Demo
{

ClassMethod Ejecutar()
{
    Do ..Limpiar()
    Do ..Herencia(.ids)
    Do ..ArbolPadreHijo(.ids)
    Do ..FallaRequerido()
    Do ..Atomicidad()
    Do ..MaquinaDeEstados(.ids)
    Do ..TransicionIlegalDeEvento()
    Do ..Inalterabilidad(.ids)
    Do ..Navegacion(.ids)
    Do ..ProyeccionSQL()
    Do ..Integridad(.ids)
    Do ..Titulo("FIN DE LA DEMOSTRACION")
}

/// Borra todos los datos de las clases del dominio (respetando la cascada).
ClassMethod Limpiar()
{
    Do ##class(Fixture.Partido).%DeleteExtent()
    Do ##class(Fixture.Persona).%DeleteExtent()
    Write "Datos previos borrados.", !
}

/// RF4 - Herencia: tres subclases de Persona.
ClassMethod Herencia(ByRef ids)
{
    Do ..Titulo("1. HERENCIA: Jugador, Arbitro y Tecnico extienden Persona (RF4)")

    Set j = ##class(Fixture.Jugador).%New()
    Set j.Nombre = "Lionel Messi", j.Nacionalidad = "ARG", j.Numero = 10, j.Posicion = "Delantero"
    Do ..Resultado("Guardar Jugador Lionel Messi", j.%Save(), 1)
    Set ids("messi") = j.%Id()

    Set j2 = ##class(Fixture.Jugador).%New()
    Set j2.Nombre = "Julian Ferreyra", j2.Nacionalidad = "ARG", j2.Numero = 9, j2.Posicion = "Delantero"
    Do ..Resultado("Guardar Jugador Julian Ferreyra", j2.%Save(), 1)
    Set ids("ferreyra") = j2.%Id()

    Set j3 = ##class(Fixture.Jugador).%New()
    Set j3.Nombre = "Youssef Amrani", j3.Nacionalidad = "MAR", j3.Numero = 4, j3.Posicion = "Defensor"
    Do ..Resultado("Guardar Jugador Youssef Amrani", j3.%Save(), 1)
    Set ids("amrani") = j3.%Id()

    Set a = ##class(Fixture.Arbitro).%New()
    Set a.Nombre = "Marta Ruiz", a.Nacionalidad = "ESP", a.Rol = "Principal"
    Do ..Resultado("Guardar Arbitro Marta Ruiz (Principal)", a.%Save(), 1)
    Set ids("arbitro") = a.%Id()

    Set a2 = ##class(Fixture.Arbitro).%New()
    Set a2.Nombre = "Pedro Alves", a2.Nacionalidad = "POR", a2.Rol = "VAR"
    Do ..Resultado("Guardar Arbitro Pedro Alves (VAR)", a2.%Save(), 1)
    Set ids("var") = a2.%Id()

    Set t = ##class(Fixture.Tecnico).%New()
    Set t.Nombre = "Ramon Duarte", t.Nacionalidad = "URU", t.Seleccion = "PAR"
    Do ..Resultado("Guardar Tecnico Ramon Duarte", t.%Save(), 1)

    Write !, "   Todos comparten el extent de Persona (IDs correlativos):", !
    Write "   ", j.%ClassName(1), " ID=", j.%Id(), " | ", a.%ClassName(1), " ID=", a.%Id(), " | ", t.%ClassName(1), " ID=", t.%Id(), !
}

/// RF6 - Arbol padre-hijo guardado con un solo %Save del padre.
ClassMethod ArbolPadreHijo(ByRef ids)
{
    Do ..Titulo("2. ARBOL PADRE-HIJO CON UN SOLO %Save (RF3, RF6)")

    Set p = ##class(Fixture.Partido).%New()
    Set p.Codigo = "M001", p.Sede = "Buenos Aires", p.Local = "ARG", p.Visitante = "MAR"
    Set p.Arbitro = ##class(Fixture.Arbitro).%OpenId(ids("arbitro"))

    Set e1 = ##class(Fixture.Evento).%New()
    Set e1.Tipo = "Gol", e1.Minuto = 15
    Set e1.Jugador = ##class(Fixture.Jugador).%OpenId(ids("messi"))
    Do p.Eventos.Insert(e1)

    Set e2 = ##class(Fixture.Evento).%New()
    Set e2.Tipo = "Amarilla", e2.Minuto = 38
    Set e2.Jugador = ##class(Fixture.Jugador).%OpenId(ids("amrani"))
    Do p.Eventos.Insert(e2)

    Write "   Antes de guardar: ID partido='", p.%Id(), "' ID evento='", e1.%Id(), "' (vacios: solo viven en memoria)", !
    Do ..Resultado("p.%Save() -- nunca se llama a %Save() sobre los eventos", p.%Save(), 1)
    Write "   Despues: ID partido=", p.%Id(), " | IDs eventos=", e1.%Id(), " y ", e2.%Id(), !
    Set ids("partido") = p.%Id(), ids("evento") = e1.%Id()
    // Se sueltan las referencias para que AsignarArbitro abra el partido fresco desde disco
    Kill p, e1, e2

    Do ..Resultado("Asignar como arbitro del partido a un arbitro VAR (debe fallar)", ..AsignarArbitro("M001", ids("var")), 0)
}

ClassMethod AsignarArbitro(pCodigo As %String, pArbitroId As %String) As %Status
{
    Set p = ##class(Fixture.Partido).CodigoIdxOpen(pCodigo)
    Set p.Arbitro = ##class(Fixture.Arbitro).%OpenId(pArbitroId)
    Quit p.%Save()
}

/// 5.3 - Falla controlada por propiedad obligatoria omitida.
ClassMethod FallaRequerido()
{
    Do ..Titulo("3. FALLA CONTROLADA: FALTA UNA PROPIEDAD OBLIGATORIA (RF5)")
    Set x = ##class(Fixture.Jugador).%New()
    Set x.Nombre = "Jugador sin dorsal", x.Nacionalidad = "ESP", x.Posicion = "Defensor"
    Do ..Resultado("Guardar Jugador sin Numero [Required]", x.%Save(), 0)

    Set y = ##class(Fixture.Jugador).%New()
    Set y.Nombre = "Dorsal invalido", y.Nacionalidad = "ESP", y.Numero = 150, y.Posicion = "Lateral"
    Do ..Resultado("Guardar Jugador con Numero=150 y Posicion='Lateral' (tipos estrictos)", y.%Save(), 0)

    Set z = ##class(Fixture.Jugador).%New()
    Set z.Nombre = "Nacionalidad invalida", z.Nacionalidad = "Argentina", z.Numero = 5, z.Posicion = "Defensor"
    Do ..Resultado("Guardar Jugador con Nacionalidad='Argentina' (patron 3 mayusculas)", z.%Save(), 0)
}

/// Si un hijo es invalido, no se guarda nada del arbol (ni el padre).
ClassMethod Atomicidad()
{
    Do ..Titulo("4. ATOMICIDAD: UN HIJO INVALIDO CANCELA TODO EL ARBOL")
    Set p = ##class(Fixture.Partido).%New()
    Set p.Codigo = "M002", p.Sede = "Madrid", p.Local = "ESP", p.Visitante = "POR"

    Set ok = ##class(Fixture.Evento).%New()
    Set ok.Tipo = "Gol", ok.Minuto = 10
    Do p.Eventos.Insert(ok)

    Set mal = ##class(Fixture.Evento).%New()
    Set mal.Tipo = "Penal", mal.Minuto = 20
    Do p.Eventos.Insert(mal)

    Do ..Resultado("Guardar Partido M002 con un evento valido y uno de Tipo 'Penal'", p.%Save(), 0)
    Write "   Existe M002 en la base? ", ##class(Fixture.Partido).CodigoIdxExists("M002"), "  (0 = no se guardo ni el padre ni el evento valido)", !
}

/// RF9 - Maquina de estados del partido.
ClassMethod MaquinaDeEstados(ByRef ids)
{
    Do ..Titulo("5. MAQUINA DE ESTADOS DEL PARTIDO (RF9)")
    Set p = ##class(Fixture.Partido).CodigoIdxOpen("M001")
    Do ..Resultado("CambiarEstado Pendiente -> Finalizado (saltea EnJuego)", p.CambiarEstado("Finalizado"), 0)
    Do ..Resultado("CambiarEstado Pendiente -> EnJuego", p.CambiarEstado("EnJuego"), 1)

    Set ev = ##class(Fixture.Evento).%New()
    Set ev.Tipo = "Gol", ev.Minuto = 67
    Set ev.Jugador = ##class(Fixture.Jugador).%OpenId(ids("ferreyra"))
    Do p.Eventos.Insert(ev)
    Do ..Resultado("Registrar Gol de Ferreyra al minuto 67 con el partido EnJuego", p.%Save(), 1)

    Do ..Resultado("CambiarEstado EnJuego -> Finalizado", p.CambiarEstado("Finalizado"), 1)
    Do ..Resultado("CambiarEstado Finalizado -> EnJuego (retroceso)", p.CambiarEstado("EnJuego"), 0)

    // Saltear el metodo y tocar la propiedad directo: igual lo frena %OnBeforeSave
    Set p.Estado = "Pendiente"
    Do ..Resultado("Set p.Estado=""Pendiente"" + %Save() directo (sin el metodo)", p.%Save(), 0)
}

/// RF9 - El caso de la consigna: evento en el minuto 0 a un partido Finalizado.
ClassMethod TransicionIlegalDeEvento()
{
    Do ..Titulo("6. EVENTOS ILEGALES (RF9)")
    // Partido auxiliar en juego para separar las dos reglas
    Set p = ##class(Fixture.Partido).%New()
    Set p.Codigo = "M003", p.Sede = "Montevideo", p.Local = "URU", p.Visitante = "PAR"
    Do p.%Save()
    Do p.CambiarEstado("EnJuego")
    Kill p

    Do ..Resultado("Evento minuto 0 en M001 (Finalizado) -- caso de la consigna", ..AgregarEvento("M001", "Gol", 0), 0)
    Do ..Resultado("Evento minuto 50 en M001 (Finalizado)", ..AgregarEvento("M001", "Gol", 50), 0)
    Do ..Resultado("Evento minuto 0 en M003 (EnJuego)", ..AgregarEvento("M003", "Gol", 0), 0)
    Do ..Resultado("Evento minuto 30 en M003 (EnJuego)", ..AgregarEvento("M003", "Gol", 30), 1)
}

/// Abre el partido fresco desde disco, le agrega un evento y lo guarda.
ClassMethod AgregarEvento(pCodigo As %String, pTipo As %String, pMinuto As %Integer) As %Status
{
    Set p = ##class(Fixture.Partido).CodigoIdxOpen(pCodigo)
    Set e = ##class(Fixture.Evento).%New()
    Set e.Tipo = pTipo, e.Minuto = pMinuto
    Do p.Eventos.Insert(e)
    Quit p.%Save()
}

/// Los eventos ya registrados no se pueden modificar.
ClassMethod Inalterabilidad(ByRef ids)
{
    Do ..Titulo("7. EVENTOS INALTERABLES")
    Set e = ##class(Fixture.Evento).%OpenId(ids("evento"))
    Write "   Evento ", e.%Id(), ": ", e.Tipo, " al minuto ", e.Minuto, !
    Set e.Minuto = 16
    Do ..Resultado("Cambiar el minuto del evento ya guardado", e.%Save(), 0)
}

/// RF7 - Consulta navegando referencias, sin SQL.
ClassMethod Navegacion(ByRef ids)
{
    Do ..Titulo("8. NAVEGACION POR REFERENCIAS, SIN SQL (RF7)")
    Set p = ##class(Fixture.Partido).%OpenId(ids("partido"))
    Write "   Partido ", p.Codigo, " en ", p.Sede, ": ", p.Local, " vs ", p.Visitante, " - Estado ", p.Estado, !
    Write "   Arbitro: ", p.Arbitro.Nombre, " (", p.Arbitro.Nacionalidad, ")", !
    Write "   Eventos (", p.Eventos.Count(), "):", !
    Set key = ""
    For {
        Set ev = p.Eventos.GetNext(.key)
        Quit:(key = "")
        Write "     min ", ev.Minuto, " - ", ev.Tipo
        If $IsObject(ev.Jugador) {
            Write " - ", ev.Jugador.Nombre, " (#", ev.Jugador.Numero, ")"
        }
        Write !
    }
    Write "   Primer evento con GetAt(1): ", p.Eventos.GetAt(1).Tipo, !

    // Navegacion inversa: desde el jugador hacia sus eventos y sus partidos
    Set j = ##class(Fixture.Jugador).%OpenId(ids("messi"))
    Write !, "   Eventos de ", j.Nombre, ":", !
    Set key = ""
    For {
        Set ev = j.Eventos.GetNext(.key)
        Quit:(key = "")
        Write "     ", ev.Tipo, " al minuto ", ev.Minuto, " en el partido ", ev.Partido.Codigo, " (", ev.Partido.Sede, ")", !
    }
}

/// RF8 - Los mismos objetos, vistos como tablas SQL.
ClassMethod ProyeccionSQL()
{
    Do ..Titulo("9. PROYECCION MULTIMODELO: LOS OBJETOS COMO TABLAS SQL (RF8)")
    Do ..SQL("SELECT ID, Nombre, Nacionalidad FROM Fixture.Persona WHERE Nacionalidad = 'ARG'")
    Do ..SQL("SELECT ID, Nombre, Numero, Posicion FROM Fixture.Jugador ORDER BY Numero")
    Do ..SQL("SELECT ID, Codigo, Sede, Estado, Arbitro->Nombre AS Arbitro FROM Fixture.Partido")
    Do ..SQL("SELECT ID, Partido->Codigo AS Partido, Minuto, Tipo, Jugador->Nombre AS Jugador FROM Fixture.Evento ORDER BY Partido, Minuto")
}

ClassMethod SQL(pSQL As %String)
{
    Write !, "   SQL> ", pSQL, !
    Set rs = ##class(%SQL.Statement).%ExecDirect(, pSQL)
    If rs.%SQLCODE < 0 {
        Write "   Error SQL ", rs.%SQLCODE, ": ", rs.%Message, !
        Quit
    }
    Do rs.%Display()
    Write !
}

/// Matriz de integridad: que pasa al borrar.
ClassMethod Integridad(ByRef ids)
{
    Do ..Titulo("10. INTEGRIDAD REFERENCIAL AL BORRAR")
    Do ..Resultado("Borrar a Messi (tiene eventos registrados)", ##class(Fixture.Jugador).%DeleteId(ids("messi")), 0)
    Do ..Resultado("Borrar a la arbitro Ruiz (dirige M001)", ##class(Fixture.Arbitro).%DeleteId(ids("arbitro")), 0)

    // Partido descartable para mostrar la cascada sin perder M001
    Set p = ##class(Fixture.Partido).%New()
    Set p.Codigo = "M004", p.Sede = "Rabat", p.Local = "MAR", p.Visitante = "ESP"
    For min = 12, 55 {
        Set e = ##class(Fixture.Evento).%New()
        Set e.Tipo = "Amarilla", e.Minuto = min
        Do p.Eventos.Insert(e)
    }
    Do p.%Save()
    Set pid = p.%Id(), eid = e.%Id()
    Write "   M004 creado con ", p.Eventos.Count(), " eventos. Existe el evento ", eid, "? ", ##class(Fixture.Evento).%ExistsId(eid), !
    Kill p, e
    Do ..Resultado("Borrar el partido M004", ##class(Fixture.Partido).%DeleteId(pid), 1)
    Write "   Existe el evento ", eid, " despues de borrar su partido? ", ##class(Fixture.Evento).%ExistsId(eid), "  (0 = se borro en cascada)", !
}

ClassMethod Titulo(pTexto As %String)
{
    Write !, "==================================================================", !
    Write pTexto, !
    Write "==================================================================", !
}

/// Imprime el resultado de una operacion y si coincide con lo esperado.
ClassMethod Resultado(pAccion As %String, pSC As %Status, pEsperaExito As %Boolean = 1)
{
    Set tExito = $$$ISOK(pSC)
    Write "   ", $Select(tExito: "[OK]        ", 1: "[RECHAZADO] "), pAccion
    Write $Select(tExito = pEsperaExito: "  (esperado)", 1: "  (INESPERADO!)"), !
    If 'tExito {
        Write "               -> ", $System.Status.GetErrorText(pSC), !
    }
}

}
