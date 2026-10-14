/// Soporte para el Hito 10 (API REST integrada). No reemplaza ni modifica las
/// clases del Hito 9 (Persona/Jugador/Arbitro/Tecnico/Partido/Evento): las usa
/// tal como estan. Esta clase solo junta la respuesta en JSON para que el
/// adaptador Python la reciba lista, sin tener que reconstruir objetos ni
/// recorrer relaciones desde afuera (la integridad y la navegacion siguen
/// viviendo adentro de IRIS, no en la API -- RF8, RNF5).
Class Fixture.ApiSupport Extends %RegisteredObject
{

/// Detalle completo de un partido: datos propios, arbitro y sus eventos con
/// el jugador que los protagonizo. Devuelve {"encontrado":false} si el
/// codigo no existe -- la API traduce eso a 404, no a un error.
ClassMethod ObtenerPartidoDetalle(pCodigo As %String) As %String
{
    Set partido = ##class(Fixture.Partido).CodigoIdxOpen(pCodigo,, .sc)
    If '$IsObject(partido) {
        Quit "{""encontrado"":false}"
    }

    Set obj = {}
    Do obj.%Set("encontrado", 1)
    Do obj.%Set("codigo", partido.Codigo)
    Do obj.%Set("sede", partido.Sede)
    Do obj.%Set("local", partido.Local)
    Do obj.%Set("visitante", partido.Visitante)
    Do obj.%Set("estado", partido.Estado)

    Set nombreArbitro = ""
    If $IsObject(partido.Arbitro) {
        Set nombreArbitro = partido.Arbitro.Nombre
    }
    Do obj.%Set("arbitro", nombreArbitro)

    Set eventos = []
    Set cantidad = partido.Eventos.Count()
    For i=1:1:cantidad {
        Set ev = partido.Eventos.GetAt(i)
        Set e = {}
        Do e.%Set("tipo", ev.Tipo)
        Do e.%Set("minuto", ev.Minuto)
        Set nombreJugador = ""
        If $IsObject(ev.Jugador) {
            Set nombreJugador = ev.Jugador.Nombre
        }
        Do e.%Set("jugador", nombreJugador)
        Do eventos.%Push(e)
    }
    Do obj.%Set("eventos", eventos)

    Quit obj.%ToJSON()
}

/// Avanza el estado de un partido usando el metodo encapsulado del dominio
/// (Partido.CambiarEstado), no un UPDATE directo: la maquina de estados y el
/// resto de %OnBeforeSave se evaluan igual que en el Hito 9.
ClassMethod CambiarEstadoPartido(pCodigo As %String, pNuevoEstado As %String) As %String
{
    Set partido = ##class(Fixture.Partido).CodigoIdxOpen(pCodigo,, .sc)
    If '$IsObject(partido) {
        Quit "{""ok"":false,""motivo"":""no_existe""}"
    }

    Set estadoAnterior = partido.Estado

    // Idempotencia (RF19): pedir el mismo estado que ya tiene no es un error.
    If (estadoAnterior = pNuevoEstado) {
        Set obj = {}
        Do obj.%Set("ok", 1)
        Do obj.%Set("estado_anterior", estadoAnterior)
        Do obj.%Set("estado_actual", partido.Estado)
        Do obj.%Set("sin_cambios", 1)
        Quit obj.%ToJSON()
    }

    Set sc = partido.CambiarEstado(pNuevoEstado)
    If $$$ISERR(sc) {
        Set obj = {}
        Do obj.%Set("ok", 0)
        Do obj.%Set("motivo", "transicion_invalida")
        Do obj.%Set("estado_actual", estadoAnterior)
        Quit obj.%ToJSON()
    }

    Set obj = {}
    Do obj.%Set("ok", 1)
    Do obj.%Set("estado_anterior", estadoAnterior)
    Do obj.%Set("estado_actual", partido.Estado)
    Do obj.%Set("sin_cambios", 0)
    Quit obj.%ToJSON()
}

}
