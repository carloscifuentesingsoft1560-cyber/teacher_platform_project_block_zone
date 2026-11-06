"""Contrato R2-A. No hay entrada operativa ni ejecución independiente autorizada."""
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from configuracion.migraciones_historicas_aisladas import BarreraHistorica, RegistroEjecucion, leer_json


def procesar_solicitud(registro, texto):
    if type(registro) is not RegistroEjecucion:
        raise BarreraHistorica('Falta el contexto en memoria del padre autorizado.')
    mensaje = leer_json(texto)
    if type(mensaje) is not dict or set(mensaje) != {'version', 'operacion', 'manifiesto', 'historial', 'pasos'}:
        raise BarreraHistorica('Parámetros arbitrarios no admitidos.')
    if type(mensaje['version']) is not int or mensaje['version'] != 1 or mensaje['operacion'] != 'validar_plan_simulado':
        raise BarreraHistorica('No se permite migrar, fake, SQL ni alterar triggers/historial.')
    return registro.consumir(mensaje['manifiesto'], mensaje['historial'], mensaje['pasos'])


def main(argv=None):
    # Ni un manifiesto en disco ni un argumento CLI crean un contexto autorizado.
    raise BarreraHistorica('Invocación independiente rechazada. R2-A no crea bases ni ejecuta procesos históricos.')


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except BarreraHistorica as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
