"""Integración real contra zona_bloque, con datos ficticios y rollback."""
from datetime import timedelta
import hashlib
from urllib.parse import parse_qs, urlsplit
import uuid

from django.conf import settings
from django.core.cache import cache
from django.db import connection, transaction, IntegrityError
from django.db.migrations.recorder import MigrationRecorder
from django.test.utils import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from cuentas.models import Usuario, SolicitudRestablecimiento
from auditoria.models import CambioAdministrativo
from organizacion.models import Grupo, Nivel, Disciplina

comprobaciones = 0
prefijo = "verif_" + uuid.uuid4().hex[:10]
clave = "Clave-ficticia-integracion-9374!"
nueva = "Nueva-clave-ficticia-integracion-5728!"


def comprobar(condicion, mensaje):
    global comprobaciones
    if not condicion:
        raise AssertionError("Fallo de integración: " + mensaje)
    comprobaciones += 1


def token_csrf(cliente):
    respuesta = cliente.get("/api/autenticacion/csrf/")
    comprobar(respuesta.status_code == 200, "obtener CSRF")
    return respuesta.json()["csrfToken"]


def escribir(cliente, ruta, datos, metodo="post"):
    csrf = token_csrf(cliente)
    return getattr(cliente, metodo)(ruta, datos, format="json", HTTP_X_CSRFTOKEN=csrf)


def ingresar(nombre, contrasena=clave):
    cliente = APIClient(enforce_csrf_checks=True)
    respuesta = escribir(cliente, "/api/autenticacion/ingresar/", {"usuario": nombre, "contrasena": contrasena})
    comprobar(respuesta.status_code == 200, "login con sesión real")
    comprobar(bool(respuesta.cookies["sessionid"]["httponly"]), "cookie HttpOnly")
    return cliente


def prueba():
    comprobar(connection.vendor == "postgresql" and connection.settings_dict["NAME"] == "zona_bloque", "destino configurado")
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        comprobar(cursor.fetchone()[0] == "zona_bloque", "destino efectivo")
    aprobadas = {("auditoria", "0001_initial"), ("cuentas", "0003_solicitudrestablecimiento"), ("organizacion", "0001_initial"), ("organizacion", "0002_catalogos_iniciales")}
    comprobar(aprobadas.issubset(MigrationRecorder(connection).applied_migrations()), "registro de migraciones")

    # La política actual no permite crear un segundo coordinador ni alterar al real.
    if ("cuentas", "0004_usuario_un_coordinador_activo") not in MigrationRecorder(connection).applied_migrations():
        raise RuntimeError("La migración de coordinador único debe estar aprobada y aplicada antes de esta prueba escritora.")
    if Usuario.objects.filter(rol="coordinador", is_active=True).exists():
        raise RuntimeError("Esta prueba requiere una base de pruebas o un cargo vacante; no se modifica al coordinador real.")

    with override_settings(ALLOWED_HOSTS=["testserver"]), transaction.atomic():
        try:
            cache.clear()
            administrador = Usuario.objects.create_user(username=prefijo+"_admin", password=clave, rol="administrador")
            anonimo = APIClient(enforce_csrf_checks=True)
            comprobar(anonimo.post("/api/autenticacion/ingresar/", {}, format="json").status_code == 403, "CSRF anónimo")
            admin = ingresar(administrador.username)
            usuarios = {}
            for sufijo, rol in [("prof", "profesor"), ("coord", "coordinador"), ("ajeno", "profesor")]:
                respuesta = escribir(admin, "/api/usuarios/", {"username": prefijo+"_"+sufijo, "rol": rol, "contrasena": clave})
                comprobar(respuesta.status_code == 201, "alta ficticia de " + rol)
                comprobar("contrasena" not in respuesta.data and "password" not in respuesta.data, "respuesta sin contraseña")
                usuarios[sufijo] = respuesta.data
            consulta = admin.get("/api/usuarios/", {"search": prefijo})
            comprobar(consulta.status_code == 200 and consulta.data["count"] == 4, "búsqueda acotada a cuentas ficticias")
            comprobar(escribir(admin, "/api/usuarios/"+str(usuarios["prof"]["id"])+"/", {"first_name": "Persona ficticia"}, "patch").status_code == 200, "edición auditada")
            comprobar(CambioAdministrativo.objects.filter(actor=administrador, accion="modificar").exists(), "actor de auditoría")

            disciplina = Disciplina.objects.get(codigo="escalada")
            niveles = set(Nivel.objects.filter(disciplina=disciplina).values_list("nombre", flat=True))
            comprobar({"Lúdico", "Nivel 1", "Nivel 2", "Escuela de especialización semicompetitiva", "Alto rendimiento"}.issubset(niveles), "cinco niveles iniciales")
            nivel = Nivel.objects.get(disciplina=disciplina, codigo="nivel-1")
            hoy = timezone.localdate()
            respuesta = escribir(admin, "/api/organizacion/periodos/", {"codigo": prefijo, "nombre": "Ciclo ficticio de integración", "fecha_inicio": str(hoy-timedelta(days=30)), "fecha_fin": str(hoy+timedelta(days=30))})
            comprobar(respuesta.status_code == 201, "crear periodo")
            periodo_id = respuesta.data["id"]
            grupos = {}
            for sufijo, inicio, fin in [("a", "10:00", "12:00"), ("b", "11:00", "13:00")]:
                respuesta = escribir(admin, "/api/organizacion/grupos/", {
                    "codigo": prefijo+"-"+sufijo, "nombre": "Grupo ficticio "+sufijo,
                    "disciplina": disciplina.pk, "nivel": nivel.pk, "periodo": periodo_id, "cupo_maximo": 10,
                    "horarios": [{"dia": hoy.weekday(), "hora_inicio": inicio, "hora_fin": fin}],
                })
                comprobar(respuesta.status_code == 201, "crear grupo y horario " + sufijo)
                grupos[sufijo] = respuesta.data["id"]

            asignacion = None
            for persona, grupo, tipo in [("prof", "a", "profesor"), ("coord", "a", "coordinador"), ("ajeno", "b", "profesor")]:
                respuesta = escribir(admin, "/api/organizacion/asignaciones/", {
                    "usuario": usuarios[persona]["id"], "grupo": grupos[grupo], "tipo": tipo,
                    "fecha_inicio": str(hoy-timedelta(days=7)),
                })
                comprobar(respuesta.status_code == 201, "asignar " + persona)
                if persona == "prof":
                    asignacion = respuesta.data["id"]
            datos = {"usuario": usuarios["prof"]["id"], "grupo": grupos["a"], "tipo": "profesor", "fecha_inicio": str(hoy)}
            comprobar(escribir(admin, "/api/organizacion/asignaciones/", datos).status_code == 400, "rechazar duplicación solapada")
            datos["grupo"] = grupos["b"]
            comprobar(escribir(admin, "/api/organizacion/asignaciones/", datos).status_code == 400, "rechazar cruce docente")
            prof = ingresar(usuarios["prof"]["username"])
            coord = ingresar(usuarios["coord"]["username"])
            for cliente in [prof, coord]:
                respuesta = cliente.get("/api/organizacion/grupos/")
                comprobar(respuesta.status_code == 200 and {g["id"] for g in respuesta.data["results"]} == ({grupos["a"]} if cliente is prof else {grupos["a"], grupos["b"]}), "alcance por rol")
                comprobar(cliente.get("/api/organizacion/grupos/"+str(grupos["b"])+"/").status_code == (404 if cliente is prof else 200), "alcance de detalle por rol")
                comprobar(escribir(cliente, "/api/usuarios/", {"username": prefijo+"_prohibido"}).status_code == 403, "rechazar administración sin rol")
            profesores = coord.get("/api/organizacion/profesores/")
            comprobar({p["id"] for p in profesores.data["results"]} == {usuarios["prof"]["id"], usuarios["ajeno"]["id"]}, "plantilla completa del coordinador")
            calendario = prof.get("/api/organizacion/calendario/", {"desde": str(hoy), "hasta": str(hoy)})
            comprobar(calendario.status_code == 200 and [e["grupo"] for e in calendario.data["eventos"]] == [grupos["a"]], "calendario de PostgreSQL")
            comprobar(prof.patch("/api/organizacion/grupos/"+str(grupos["a"])+"/", {}, format="json").status_code == 403, "CSRF y permisos de escritura")
            restriccion = False
            try:
                with transaction.atomic():
                    Grupo.objects.filter(pk=grupos["a"]).update(cupo_maximo=0)
            except IntegrityError:
                restriccion = True
            comprobar(restriccion and Grupo.objects.get(pk=grupos["a"]).cupo_maximo == 10, "restricción PostgreSQL y savepoint")

            ruta_usuario = "/api/usuarios/"+str(usuarios["prof"]["id"])+"/"
            respuesta = escribir(admin, ruta_usuario+"restablecer-acceso/", {"contrasena_actual": "incorrecta"})
            comprobar(respuesta.status_code == 400, "reautenticación de recuperación")
            respuesta = escribir(admin, ruta_usuario+"restablecer-acceso/", {"contrasena_actual": clave})
            comprobar(respuesta.status_code == 200, "emitir enlace privado")
            token = parse_qs(urlsplit(respuesta.data["ruta"]).fragment)["token"][0]
            solicitud = SolicitudRestablecimiento.objects.get(usuario_id=usuarios["prof"]["id"])
            comprobar(solicitud.token_hash == hashlib.sha256(token.encode()).hexdigest(), "guardar solo hash")
            publico = APIClient(enforce_csrf_checks=True)
            datos = {"token": token, "contrasena": nueva}
            comprobar(escribir(publico, "/api/recuperacion/confirmar/", datos).status_code == 200, "consumir recuperación")
            comprobar(escribir(publico, "/api/recuperacion/confirmar/", datos).status_code == 400, "token de un solo uso")
            comprobar(prof.get("/api/autenticacion/sesion/").status_code == 403, "revocar sesión anterior")
            prof = ingresar(usuarios["prof"]["username"], nueva)
            comprobar(escribir(admin, ruta_usuario, {"is_active": False}, "patch").status_code == 200, "desactivar cuenta")
            comprobar(prof.get("/api/autenticacion/sesion/").status_code == 403, "revocación por estado")
            comprobar(escribir(admin, ruta_usuario, {"is_active": True}, "patch").status_code == 200, "reactivar cuenta")
            comprobar(escribir(admin, "/api/organizacion/asignaciones/"+str(asignacion)+"/finalizar/", {"fecha_fin": str(hoy-timedelta(days=1))}).status_code == 200, "finalizar con historial")
            prof = ingresar(usuarios["prof"]["username"], nueva)
            comprobar(prof.get("/api/organizacion/grupos/").data["count"] == 0, "revocación por fin de asignación")
            comprobar(escribir(admin, ruta_usuario, {}, "delete").status_code == 405, "sin eliminación de cuentas")
            comprobar(escribir(admin, "/api/organizacion/grupos/"+str(grupos["a"])+"/", {}, "delete").status_code == 405, "sin eliminación de grupos")
            comprobar(escribir(prof, "/api/autenticacion/salir/", {}).status_code == 200, "logout")
            comprobar(prof.get("/api/autenticacion/sesion/").status_code == 403, "logout revoca sesión")
        finally:
            transaction.set_rollback(True)
    comprobar(not Usuario.objects.filter(username__startswith=prefijo).exists(), "rollback de usuarios ficticios")
    comprobar(not Grupo.objects.filter(codigo__startswith=prefijo).exists(), "rollback de grupos ficticios")
    print("Integración PostgreSQL zona_bloque: " + str(comprobaciones) + " comprobaciones aprobadas; datos ficticios revertidos.")


prueba()
