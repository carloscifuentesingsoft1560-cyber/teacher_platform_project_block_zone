"""Receptor documental R2-B1 en memoria: no inicia Django ni procesos."""
from postgresql_historico_controlado import (
    BarreraProtocolo, ContextoHijoSimulado, RegistroDocumentalSimulado,
    configuracion_propuesta, validar_configuracion,
)


class HijoDocumentalSimulado:
    def __init__(self, contexto):
        if type(contexto) is not ContextoHijoSimulado or type(contexto._padre) is not RegistroDocumentalSimulado:
            raise BarreraProtocolo('Invocación sin contexto privado rechazada.')
        contexto._padre._capacidad(contexto)
        self._contexto = contexto

    def recibir(self, trama, observacion, ahora_ms):
        return self._contexto._padre.recibir_en_hijo(
            self._contexto, trama, observacion, ahora_ms)

    def describir_configuracion(self, propuesta=None):
        padre = self._contexto._padre
        padre._capacidad(self._contexto)
        esperada = configuracion_propuesta(padre.contexto)
        validar_configuracion(esperada if propuesta is None else propuesta, padre.contexto)
        return esperada

    def comunicar_error(self, error):
        padre = self._contexto._padre
        padre._capacidad(self._contexto)
        padre.fallar(error)


def main(argv=None):
    raise BarreraProtocolo('Hijo histórico independiente deshabilitado; solo simulación en memoria.')


if __name__ == '__main__':
    main()
