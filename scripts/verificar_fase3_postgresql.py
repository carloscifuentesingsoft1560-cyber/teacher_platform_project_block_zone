"""Integración en zona_bloque: destinos ficticios y rollback global obligatorio.

No modifica cuentas reales ni necesita sus contraseñas. Reutiliza sus identidades
solo como actores autorizados internos; nunca crea sesiones de cuentas reales.
"""
from datetime import timedelta
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
from django.db import connection,transaction
from django.utils import timezone
from rest_framework.test import APIClient
from cuentas.models import Usuario
from organizacion.models import Disciplina,Nivel,Periodo,Grupo,Horario,Asignacion
from deportistas.models import Deportista
from inscripciones.models import Inscripcion,Propuesta,EventoInscripcion
from auditoria.models import CambioAdministrativo
from aplicar_migraciones_fase3 import destino,exigir,TABLAS,huellas as huellas_originales

def huellas_completas():
    resultado={}
    with connection.cursor() as c:
        for tabla in sorted(connection.introspection.table_names()):
            c.execute("SELECT row_to_json(t)::text FROM "+connection.ops.quote_name(tabla)+" t")
            filas=sorted(r[0] for r in c.fetchall())
            resultado[tabla]={"filas":len(filas),"sha256":hashlib.sha256(json.dumps(filas,ensure_ascii=False).encode()).hexdigest()}
    return resultado

def ejecutar():
    destino()
    raiz=Path(__file__).resolve().parent.parent
    ruta=sorted((raiz/"respaldos").glob("fase3_*.json"))[-1]
    informe=json.loads(ruta.read_text(encoding="utf-8"))
    exigir(informe["estado"]=="aplicadas_y_confirmadas","Las migraciones no están confirmadas.")
    casos=[]
    cliente=APIClient(HTTP_HOST="localhost")
    hoy=timezone.localdate()
    prefijo="ficticio_f3_"+uuid4().hex[:10]
    def comprobar(condicion,nombre):
        exigir(condicion,nombre)
        casos.append(nombre)
    def estado(respuesta,esperado,nombre):
        comprobar(respuesta.status_code==esperado,nombre)
        return respuesta
    def post(ruta,datos):
        return cliente.post("/api/"+ruta,datos,format="json")
    def como(actor):
        cliente.force_authenticate(actor)
    with transaction.atomic():
        tablas=connection.introspection.table_names()
        with connection.cursor() as c:
            c.execute("SET LOCAL lock_timeout='10s'")
            c.execute("SET LOCAL statement_timeout='60s'")
            c.execute("LOCK TABLE "+", ".join(connection.ops.quote_name(t) for t in sorted(tablas))+" IN SHARE ROW EXCLUSIVE MODE")
        exigir(huellas_originales(informe["tablas_anteriores"])==informe["huellas_antes"],"Los registros anteriores cambiaron; revisar antes de probar.")
        antes=huellas_completas()
        exigir(all(antes[t]["filas"]==0 for t in TABLAS),"Hay datos reales nuevos de Fase 3: no se ejecutan fixtures sobre ellos.")
        admin=Usuario.objects.filter(rol="administrador",is_active=True).first()
        coord=Usuario.objects.get(rol="coordinador",is_active=True)
        exigir(admin is not None,"Falta administrador activo.")
        como(admin)
        estado(cliente.get("/api/paneles/administrador/resumen/?fecha=2026-10-28&periodo=4"),200,"Panel administrativo real y periodo 4 disponibles")
        como(coord)
        estado(cliente.get("/api/paneles/coordinador/resumen/"),200,"Panel coordinador real disponible")
        estado(cliente.get("/api/deportistas/"),200,"API Fase 3 habilitada y vacía")

        prof=Usuario.objects.create_user(username=prefijo+"prof",rol="profesor")
        otro=Usuario.objects.create_user(username=prefijo+"otro",rol="profesor")
        d=Disciplina.objects.create(codigo=prefijo,nombre="Disciplina ficticia de verificación")
        n=Nivel.objects.create(disciplina=d,codigo="uno",nombre="Nivel ficticio uno")
        n2=Nivel.objects.create(disciplina=d,codigo="dos",nombre="Nivel ficticio dos")
        periodo=Periodo.objects.create(codigo=prefijo,nombre="Periodo ficticio",fecha_inicio=hoy-timedelta(days=10),fecha_fin=hoy+timedelta(days=30))
        def grupo(codigo,inicio,fin,nivel=None,cupo=2):
            g=Grupo.objects.create(codigo=prefijo+codigo,nombre="Grupo ficticio "+codigo,disciplina=d,nivel=nivel or n,periodo=periodo,cupo_maximo=cupo)
            for dia in range(7):
                Horario.objects.create(grupo=g,dia=dia,hora_inicio=inicio,hora_fin=fin)
            Asignacion.objects.create(grupo=g,usuario=prof,tipo="profesor",fecha_inicio=periodo.fecha_inicio)
            return g
        a=grupo("a","10:00","11:00",cupo=1)
        b=grupo("b","11:00","12:00")
        x=grupo("x","10:30","11:30")
        l=grupo("l","12:00","13:00",n2)
        datos={"nombres":"Deportista ficticio","apellidos":"Verificación","fecha_nacimiento":str(hoy-timedelta(days=4000))}
        r=estado(post("deportistas/",datos),201,"Coordinador crea ficha mínima")
        persona=Deportista.objects.get(pk=r.data["id"])
        uuid=str(persona.identificador_publico)
        codigo=persona.codigo_interno
        estado(post("deportistas/",{**datos,"fecha_nacimiento":str(hoy+timedelta(days=1))}),400,"Nacimiento futuro rechazado")
        estado(cliente.patch("/api/deportistas/"+uuid+"/",{"nombres":"Corrección ficticia","version":1},format="json"),200,"Edición de identidad versionada")
        persona.refresh_from_db()
        comprobar(persona.codigo_interno==codigo,"Código permanente conservado")
        otra=Deportista.objects.create(nombres="Otra ficha ficticia",apellidos="Prueba",fecha_nacimiento=persona.fecha_nacimiento,creado_por=admin,actualizado_por=admin)
        como(prof)
        estado(post("deportistas/",datos),403,"Profesor no crea identidades")
        estado(cliente.get("/api/deportistas/"+uuid+"/"),404,"Profesor no ve ficha sin inscripción propia")
        estado(post("inscripciones/",{}),403,"Profesor no ejecuta inscripción")

        como(coord)
        ingreso={"deportista":persona.pk,"grupo":a.pk,"fecha_ingreso":str(hoy-timedelta(days=2)),"motivo":"Ingreso ficticio de prueba"}
        r=estado(post("inscripciones/",ingreso),201,"Inscripción inicial autorizada")
        id_a=r.data["id"]
        estado(post("inscripciones/",ingreso),409,"Inscripción duplicada rechazada")
        como(prof)
        r=estado(cliente.get("/api/deportistas/"+uuid+"/"),200,"Profesor accede a ficha propia")
        comprobar("fecha_nacimiento" not in r.data,"Ficha docente minimiza datos")
        estado(cliente.get("/api/deportistas/"+str(otra.identificador_publico)+"/"),404,"Ficha ajena oculta")
        estado(cliente.get("/api/acudientes/"),403,"Profesor sin padrón de acudientes")
        estado(post("propuestas/",{"tipo":"inscripcion","deportista":otra.pk,"grupo_destino":b.pk,"fecha_efectiva":str(hoy),"justificacion":"Fuera del ámbito"}),400,"Propuesta fuera del ámbito rechazada")
        propuesta={"tipo":"inscripcion","deportista":persona.pk,"grupo_destino":b.pk,"fecha_efectiva":str(hoy),"justificacion":"Grupo adicional compatible ficticio"}
        p=estado(post("propuestas/",propuesta),201,"Profesor propone grupo compatible")
        comprobar(Inscripcion.objects.filter(deportista=persona).count()==1,"Propuesta no ejecuta inscripción")
        estado(post(f"propuestas/{p.data['id']}/aprobar/",{"version":1,"resolucion":"No autorizado"}),403,"Profesor no aprueba")
        como(admin)
        estado(post(f"propuestas/{p.data['id']}/aprobar/",{"version":1,"resolucion":"Aprobación ficticia administrativa"}),200,"Administrador aprueba inscripción compatible")
        estado(post(f"propuestas/{p.data['id']}/aprobar/",{"version":1,"resolucion":"Repetición ficticia"}),409,"Aprobación duplicada rechazada")
        comprobar(Inscripcion.objects.filter(deportista=persona,estado="activa").count()==2,"Varios grupos compatibles conservan identidad")

        como(prof)
        p=estado(post("propuestas/",{**propuesta,"grupo_destino":x.pk}),201,"Se registra propuesta sujeta a validación final")
        como(coord)
        estado(post(f"propuestas/{p.data['id']}/aprobar/",{"version":1,"resolucion":"Prueba de cruce"}),400,"Aprobación rechaza horario incompatible")
        comprobar(Propuesta.objects.get(pk=p.data["id"]).estado=="pendiente","Conflicto revierte decisión y destino")
        como(prof)
        estado(post(f"propuestas/{p.data['id']}/cancelar/",{"version":1,"resolucion":"Retirada ficticia"}),200,"Autor cancela sin borrar historial")

        # Retira solo la asignación FICTICIA incompatible usada para probar el rechazo anterior.
        Asignacion.objects.filter(grupo=x,usuario=prof).delete()
        como(coord)
        estado(post(f"inscripciones/{id_a}/suspender/",{"version":1,"motivo":"Reserva ficticia"}),400,"Suspensión exige vencimiento explícito")
        estado(post(f"inscripciones/{id_a}/suspender/",{"version":1,"motivo":"Pausa ficticia reservada","fecha_vencimiento":str(hoy)}),200,"Suspensión conserva reserva y autor")
        r=estado(cliente.get(f"/api/inscripciones/cupos/?grupo={a.pk}&desde={hoy}&hasta={hoy}"),200,"Consulta de cupos autorizada")
        comprobar(r.data["ocupacion_maxima"]==1 and r.data["disponibles"]==0,"Reserva vigente cuenta como ocupación")
        estado(post("inscripciones/",{**ingreso,"deportista":otra.pk}),409,"Reserva impide sobrecupo")
        como(prof)
        h=estado(cliente.get(f"/api/inscripciones/{id_a}/historial/"),200,"Historial docente autorizado")
        comprobar("motivo" not in h.data["reservas"][0],"Motivo administrativo reservado a gestión")
        manana=hoy+timedelta(days=1)
        with patch("django.utils.timezone.localdate",return_value=manana):
            como(coord)
            numero=EventoInscripcion.objects.count()
            r=estado(cliente.get(f"/api/inscripciones/cupos/?grupo={a.pk}"),200,"Consulta reconoce vencimiento")
            comprobar(r.data["ocupacion_maxima"]==0 and EventoInscripcion.objects.count()==numero,"GET de cupos no modifica registros")
            r=estado(post("inscripciones/liberar-reservas/",{}),200,"Liberación transaccional de vencimiento")
            comprobar(r.data["liberadas"]==1,"Exactamente una reserva liberada")
            comprobar(post("inscripciones/liberar-reservas/",{}).data["liberadas"]==0,"Liberación repetida idempotente")
            original=Inscripcion.objects.get(pk=id_a)
            comprobar(original.causa_salida=="reserva_vencida" and original.eventos.filter(tipo="liberar_reserva").count()==1,"Inscripción histórica y evento conservados")

            r=estado(post("inscripciones/",{**ingreso,"fecha_ingreso":str(manana)}),201,"Reingreso posterior a reserva vencida")
            id_b=Inscripcion.objects.get(deportista=persona,grupo=b).pk
            como(prof)
            p=estado(post("propuestas/",{"tipo":"nivel","deportista":persona.pk,"inscripcion_origen":id_b,"grupo_destino":l.pk,"fecha_efectiva":str(manana),"justificacion":"Cambio pedagógico ficticio"}),201,"Profesor propone cambio de nivel")
            como(admin)
            estado(post(f"propuestas/{p.data['id']}/aprobar/",{"version":1,"resolucion":"No suplanta coordinación"}),403,"Administrador no suplanta decisión pedagógica")
            como(coord)
            estado(post(f"propuestas/{p.data['id']}/aprobar/",{"version":1,"resolucion":"Revisión ficticia coordinadora"}),200,"Coordinador activo decide y aplica nivel")
            antiguo=Inscripcion.objects.get(pk=id_b)
            comprobar(antiguo.estado=="finalizada" and antiguo.grupo.nivel_id==n.pk,"Nivel anterior permanece intacto")
            nuevo=Inscripcion.objects.get(inscripcion_anterior=antiguo)
            comprobar(nuevo.grupo.nivel_id==n2.pk and nuevo.deportista_id==persona.pk,"Nuevo nivel conserva identidad y origen")
            estado(cliente.patch(f"/api/organizacion/grupos/{a.pk}/",{"cupo_maximo":2},format="json"),200,"Ampliación válida de cupo")
            estado(post("inscripciones/",{**ingreso,"deportista":otra.pk,"fecha_ingreso":str(manana)}),201,"Otra ficha ocupa cupo restante")
            estado(cliente.patch(f"/api/organizacion/grupos/{a.pk}/",{"cupo_maximo":1},format="json"),400,"Reducción incompatible de cupo rechazada")
            estado(cliente.patch(f"/api/organizacion/grupos/{a.pk}/",{"horarios":[{"dia":manana.weekday(),"hora_inicio":"12:00","hora_fin":"13:00"}]},format="json"),400,"Cambio posterior de horario incompatible rechazado")
            a.refresh_from_db()
            comprobar(a.cupo_maximo==2 and a.horarios.filter(activo=True).count()==7,"Ediciones rechazadas conservan cupo y horarios")

        como(coord)
        contacto=estado(post("acudientes/",{"nombres":"Contacto ficticio","apellidos":"Prueba","telefono":"3000000000"}),201,"Acudiente con contacto mínimo")
        vinculo=estado(post("vinculos-acudientes/",{"deportista":persona.pk,"acudiente":contacto.data["id"],"fecha_inicio":str(hoy),"es_contacto_principal":True}),201,"Vínculo separado de identidad")
        comprobar(vinculo.data["facultad_para_autorizar"]=="pendiente","Contacto no concede representación")
        como(admin)
        tipo=estado(post("tipos-autorizacion/",{"codigo":prefijo,"numero_version":1,"finalidad":"Finalidad ficticia exclusiva de prueba","referencia_texto_aprobado":"Referencia ficticia; no autorización institucional real"}),201,"Tipo de prueba versionado por administrador")
        como(coord)
        autorizacion={"deportista":persona.pk,"tipo":tipo.data["id"],"otorgante":"acudiente","vinculo_acudiente":vinculo.data["id"],"decision":"otorgada","declarada_en":timezone.now().isoformat(),"vigente_desde":str(hoy),"referencia_evidencia":"referencia-privada-ficticia"}
        estado(post("autorizaciones/",autorizacion),400,"Autorización exige facultad acreditada")
        estado(post(f"vinculos-acudientes/{vinculo.data['id']}/verificar/",{"version":1}),200,"Verificación explícita registra responsable")
        au=estado(post("autorizaciones/",autorizacion),201,"Registro diferenciado de declaración ficticia")
        estado(post(f"autorizaciones/{au.data['id']}/revocar/",{"version":1,"motivo":"Revocación ficticia de prueba"}),200,"Revocación sin eliminar historia")
        comprobar(CambioAdministrativo.objects.filter(entidad="deportistas.autorizacion",identificador=au.data["id"],accion="revocar").exists(),"Revocación queda auditada")
        como(prof)
        estado(cliente.get("/api/autorizaciones/"),403,"Autorizaciones no expuestas al profesor")
        estado(post("politicas-datos/",{}),403,"Profesor no configura política")
        Usuario.objects.filter(pk=prof.pk).update(is_active=False)
        estado(cliente.get("/api/deportistas/"),403,"Revocación de cuenta ficticia invalida acceso")

        # Sesión y logout solo para una cuenta FICTICIA dentro del rollback.
        falso_admin=Usuario.objects.create_user(username=prefijo+"admin",rol="administrador")
        csrf=APIClient(enforce_csrf_checks=True,HTTP_HOST="localhost")
        csrf.force_login(falso_admin)
        estado(csrf.get("/api/paneles/administrador/resumen/"),200,"Panel administrativo mediante sesión Django ficticia")
        estado(csrf.post("/api/deportistas/",datos,format="json"),403,"Escritura por sesión exige CSRF")
        token=csrf.get("/api/autenticacion/csrf/").data["csrfToken"]
        estado(csrf.post("/api/autenticacion/salir/",{},format="json",HTTP_X_CSRFTOKEN=token),200,"Cierre de sesión con CSRF funciona")
        estado(csrf.get("/api/paneles/administrador/resumen/"),403,"Sesión cerrada no accede al panel")
        como(admin)
        estado(cliente.get("/api/paneles/administrador/resumen/"),200,"Panel administrador funciona con nuevo esquema")
        como(coord)
        estado(cliente.get("/api/paneles/coordinador/resumen/"),200,"Panel coordinador funciona con nuevo esquema")
        transaction.set_rollback(True)
    despues=huellas_completas()
    exigir(despues==antes,"Los conteos/huellas cambiaron al revertir las pruebas; revisar sin alterar registros reales.")
    informe["integracion_real_revertida"]={"comprobaciones_aprobadas":len(casos),"casos":casos,
        "todas_las_tablas_identicas":True,"datos_ficticios_persistentes":0,
        "huellas_completas_despues":despues,
        "limite":"No se simula relevo de la persona real ni concurrencia entre fixtures no confirmados; esas carreras se prueban en clúster aislado."}
    ruta.write_text(json.dumps(informe,indent=2,ensure_ascii=False),encoding="utf-8")
    print("Integración zona_bloque:",len(casos),"comprobaciones aprobadas, transacción revertida.")
    print("Todos los conteos y SHA-256 idénticos después de probar; diez tablas nuevas vacías.")
    print("Paneles administrador/coordinador disponibles; sin cambios a cuentas reales.")

if __name__=="__main__":
    ejecutar()
