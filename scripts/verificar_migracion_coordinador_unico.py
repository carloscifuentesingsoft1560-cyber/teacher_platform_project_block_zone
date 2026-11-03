"""Integración PostgreSQL con destinos ficticios revertidos; nunca cambia al titular."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4
import json
import runpy
from pathlib import Path
from django.db import connection, connections, transaction, IntegrityError
from django.utils import timezone
from rest_framework.test import APIClient
from cuentas.models import Usuario
from organizacion.models import Disciplina, Nivel, Periodo, Grupo, Horario
from auditoria.models import CambioAdministrativo

def ejecutar():
    assert connection.vendor == "postgresql" and connection.settings_dict["NAME"] == "zona_bloque"
    with connection.cursor() as c:
        c.execute("SELECT current_database()")
        assert c.fetchone()[0] == "zona_bloque"
    raiz = Path(__file__).resolve().parent.parent
    manifiesto = sorted((raiz/"respaldos").glob("coordinador_unico_*.json"))[-1]
    datos = json.loads(manifiesto.read_text(encoding="utf-8"))
    huellas = runpy.run_path(str(raiz/"scripts/aplicar_migracion_coordinador_unico.py"))["huellas"]
    antes = huellas()
    assert antes == datos["huellas_antes"], "Hubo cambios posteriores: revisar antes de probar"
    titular = Usuario.objects.get(rol="coordinador", is_active=True)
    barrera = Barrier(2)
    prefijo = "prueba_migracion_" + uuid4().hex[:10]
    def competir(numero):
        try:
            with transaction.atomic():
                with connections["default"].cursor() as c:
                    c.execute("SET LOCAL lock_timeout = '5s'")
                    c.execute("SET LOCAL statement_timeout = '10s'")
                barrera.wait(timeout=10)
                Usuario.objects.create(id=-910000-numero, username=prefijo+str(numero), rol="coordinador", is_active=True, password="!")
                transaction.set_rollback(True)
            return False
        except IntegrityError as error:
            return getattr(getattr(error.__cause__, "diag", None), "constraint_name", None) == "un_coordinador_activo"
        finally:
            connections["default"].close()
    with ThreadPoolExecutor(max_workers=2) as piscina:
        resultados = list(piscina.map(competir, [1, 2]))
    assert resultados == [True, True], "La restricción concurrente no respondió como se esperaba"
    print("Concurrencia PostgreSQL: 2/2 inserciones simultáneas de un segundo coordinador rechazadas por un_coordinador_activo.")
    pruebas = []
    def comprobar(condicion, nombre):
        assert condicion, nombre
        pruebas.append(nombre)
    cliente = APIClient(HTTP_HOST="localhost")
    hoy = timezone.localdate()
    with transaction.atomic():
        admin = Usuario.objects.create(id=1920000001, username=prefijo+"admin", rol="administrador", password="!")
        profesor = Usuario.objects.create(id=1920000002, username=prefijo+"prof", rol="profesor", password="!")
        otro = Usuario.objects.create(id=1920000003, username=prefijo+"otro", rol="profesor", password="!")
        d = Disciplina.objects.create(id=1920000001, codigo=prefijo, nombre="Disciplina ficticia")
        n = Nivel.objects.create(id=1920000001, disciplina=d, codigo=prefijo, nombre="Nivel ficticio")
        p = Periodo.objects.create(id=1920000001, codigo=prefijo, nombre="Periodo ficticio", fecha_inicio=hoy-timedelta(days=3), fecha_fin=hoy+timedelta(days=7))
        g = Grupo.objects.create(id=1920000001, codigo=prefijo+"a", nombre="Grupo ficticio A", disciplina=d, nivel=n, periodo=p, cupo_maximo=8)
        g2 = Grupo.objects.create(id=1920000002, codigo=prefijo+"b", nombre="Grupo ficticio B", disciplina=d, nivel=n, periodo=p, cupo_maximo=8)
        Horario.objects.create(id=1920000001, grupo=g, dia=hoy.weekday(), hora_inicio="10:00", hora_fin="11:00")
        Horario.objects.create(id=1920000002, grupo=g2, dia=hoy.weekday(), hora_inicio="11:00", hora_fin="12:00")
        def asignar(grupo):
            return cliente.post("/api/organizacion/asignaciones/", {"grupo":grupo.pk,"usuario":profesor.pk,"tipo":"profesor","fecha_inicio":str(hoy)}, format="json")
        cliente.force_authenticate(titular)
        comprobar(cliente.get("/api/organizacion/profesores/").status_code==200, "Coordinador consulta profesores")
        comprobar(cliente.get("/api/paneles/coordinador/resumen/").status_code==200, "Coordinador consulta su tablero")
        comprobar(cliente.post("/api/usuarios/", {"rol":"administrador"}, format="json").status_code==403, "Coordinador no crea usuarios")
        comprobar(cliente.patch(f"/api/usuarios/{profesor.pk}/", {"rol":"administrador"}, format="json").status_code==403, "Coordinador no altera roles")
        comprobar(cliente.post("/api/organizacion/disciplinas/", {}, format="json").status_code==403, "Coordinador no altera configuración")
        comprobar(cliente.get("/api/paneles/administrador/resumen/").status_code==403, "Coordinador sin tablero administrador")
        r = asignar(g)
        comprobar(r.status_code==201, "Coordinador asigna profesor")
        comprobar(asignar(g2).status_code==201, "Coordinador asigna grupo contiguo")
        comprobar(asignar(g).status_code==400, "Duplicado de asignación rechazado")
        ruta = f"/api/organizacion/grupos/{g.pk}/"
        conflicto = cliente.patch(ruta, {"horarios":[{"dia":hoy.weekday(),"hora_inicio":"10:30","hora_fin":"11:30"}]}, format="json")
        comprobar(conflicto.status_code==400, "Horario incompatible rechazado")
        comprobar(str(g.horarios.get(activo=True).hora_inicio)=="10:00:00", "Conflicto conserva horario anterior")
        correcto = cliente.patch(ruta, {"horarios":[{"dia":hoy.weekday(),"hora_inicio":"09:00","hora_fin":"10:00"}]}, format="json")
        comprobar(correcto.status_code==200, "Horario compatible autorizado")
        comprobar(g.horarios.filter(activo=False).count()==1, "Historial del horario conservado")
        comprobar(CambioAdministrativo.objects.filter(actor=titular, identificador=g.pk).exists(), "Escritura auditada")
        cliente.force_authenticate(profesor)
        comprobar(cliente.get(ruta).status_code==200, "Profesor consulta grupo propio")
        comprobar(cliente.patch(ruta, {"nombre":"No autorizado"}, format="json").status_code==403, "Profesor no coordina horarios")
        comprobar(asignar(g).status_code==403, "Profesor no asigna")
        cliente.force_authenticate(otro)
        comprobar(cliente.get(ruta).status_code==404, "Profesor ajeno sin acceso al grupo")
        cliente.force_authenticate(admin)
        comprobar(cliente.get("/api/usuarios/").status_code==200, "Administrador consulta usuarios")
        comprobar(cliente.get("/api/paneles/administrador/resumen/").status_code==200, "Administrador consulta tablero global")
        cliente.force_authenticate(None)
        comprobar(cliente.get("/api/organizacion/grupos/").status_code==403, "Anónimo sin acceso")
        transaction.set_rollback(True)
    assert huellas() == antes, "Los datos no coinciden después de revertir las pruebas"
    datos["integracion_postgresql"] = {"comprobaciones_aprobadas":len(pruebas), "casos":pruebas,
        "intentos_concurrentes_rechazados":2, "datos_intactos_tras_pruebas":True,
        "limite_concurrencia":"Dos inserciones ante titular existente; no se fuerza un relevo real ni carrera con plaza vacante."}
    manifiesto.write_text(json.dumps(datos, indent=2), encoding="utf-8")
    print("Integración PostgreSQL:", len(pruebas), "comprobaciones aprobadas; todas las escrituras ficticias revertidas.")
    print("Huellas y conteos de TODAS las tablas de datos idénticos al respaldo previo; cuentas reales intactas.")

if __name__ == "__main__":
    ejecutar()
