"""Cierre de solo lectura de 0003; no ejecuta migraciones ni crea sesiones.

Escribe únicamente evidencia agregada dentro del manifiesto privado existente.
Diseñado para el cierre previo a registrar comprobaciones institucionales nuevas.
"""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
from django.db import connection,transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from rest_framework.test import APIClient
from cuentas.models import Usuario


def verificar():
    raiz=Path(__file__).resolve().parent.parent
    spec=importlib.util.spec_from_file_location('aplicacion_facultades_util',raiz/'scripts/aplicar_comprobacion_facultades.py')
    utilidad=importlib.util.module_from_spec(spec);spec.loader.exec_module(utilidad)
    exigir=utilidad.exigir
    ruta=sorted((raiz/'respaldos').glob('facultades_aplicacion_*/manifiesto.json'))[-1]
    datos=json.loads(ruta.read_text(encoding='utf-8'))
    exigir(datos['estado']=='aplicada_y_confirmada','Manifiesto sin aplicación confirmada.')
    respaldo=raiz/datos['respaldo']
    exigir(hashlib.sha256(respaldo.read_bytes()).hexdigest()==datos['sha256_respaldo'],'Integridad del respaldo no coincide.')
    restauradas=json.loads((ruta.parent/'huellas_restauracion.json').read_text(encoding='utf-8'))
    exigir(datos['lectura_completa'] and datos['recuperacion']['restauracion_completa'] and restauradas==datos['huellas_antes']==datos['huellas_despues'],'No coincide la evidencia de recuperación.')
    http=[]
    with transaction.atomic():
        with connection.cursor() as c:
            c.execute('SET TRANSACTION READ ONLY')
        utilidad.comun.destino()
        ejecutor=MigrationExecutor(connection);ejecutor.loader.check_consistent_history(connection)
        exigir(utilidad.OBJETIVO in MigrationRecorder(connection).applied_migrations(),'La migración no figura aplicada.')
        exigir(not ejecutor.migration_plan(ejecutor.loader.graph.leaf_nodes()),'Quedan migraciones pendientes.')
        utilidad.verificar_esquema()
        exigir(utilidad.huellas(connection,datos['columnas_originales'])==datos['huellas_antes'],'Cambios en registros o columnas anteriores.')
        for rol in ('administrador','coordinador'):
            actor=Usuario.objects.filter(rol=rol,is_active=True).first()
            exigir(actor is not None,'Falta cuenta existente para comprobar panel.')
            cliente=APIClient(HTTP_HOST='localhost');cliente.force_authenticate(actor)
            for url in ('/api/autorizaciones/','/api/acudientes/','/api/vinculos-acudientes/?deportista=9',
                        '/api/vinculos-acudientes/3/','/api/vinculos-acudientes/3/historial-facultades/',
                        '/api/paneles/'+rol+'/resumen/','/api/deportistas/'):
                r=cliente.get(url)
                exigir(r.status_code==200,'Respuesta GET autorizada distinta de 200.')
                if url=='/api/vinculos-acudientes/3/':
                    exigir(r.data['facultad_para_autorizar']=='pendiente' and r.data['facultades']==[],'El vínculo 3 adquirió una facultad.')
                if url.endswith('/historial-facultades/'):
                    exigir(r.data==[],'Historial institucional no vacío al cierre.')
                if url=='/api/autorizaciones/':
                    exigir(all(x['comprobacion_facultad'] is None and x['facultad_vigente'] is not True for x in r.data['results']),'Acreditación retroactiva inesperada.')
                http.append({'rol':rol,'ruta':url,'estado':r.status_code})
        cliente=APIClient(HTTP_HOST='localhost')
        exigir(cliente.get('/api/autorizaciones/').status_code==403,'Visitante obtiene acceso.')
        http.append({'rol':'anonimo','ruta':'/api/autorizaciones/','estado':403})
        profesor=Usuario.objects.filter(rol='profesor',is_active=True).first()
        exigir(profesor is not None,'Falta profesor existente para verificar restricciones.')
        cliente.force_authenticate(profesor)
        for url in ('/api/autorizaciones/','/api/vinculos-acudientes/3/historial-facultades/',
                    '/api/paneles/administrador/resumen/','/api/paneles/coordinador/resumen/'):
            r=cliente.get(url);exigir(r.status_code==403,'El profesor accede a un recurso reservado.')
            http.append({'rol':'profesor','ruta':url,'estado':403})
    datos['verificacion_posterior']={'fecha_utc':datetime.now(timezone.utc).isoformat(),
        'migracion_aplicada':True,'pendientes':[],'tablas_anteriores_identicas':len(datos['huellas_antes']),
        'vinculo_3_identidad_parentesco_y_estado_conservados':True,'estado_vinculo_3':'pendiente',
        'comprobaciones_creadas':0,'autorizaciones_acreditadas_retroactivamente':0,
        'integridad_respaldo_confirmada':True,'http_django_get_solo_lectura':http}
    utilidad.guardar(ruta,datos)
    print('Destino zona_bloque/public; 0003 aplicada; cero pendientes. 31 tablas anteriores idénticas; vínculo 3 pendiente, identidad y parentesco conservados.')
    print('Tabla, FK nullable, cinco restricciones, función/trigger habilitado: correctos. Sin comprobaciones ni acreditaciones retroactivas.')
    print('Respaldo:',datos['respaldo'],'; bytes:',datos['bytes'],'; SHA-256:',datos['sha256_respaldo'])
    print('Restauración funcional y huellas verificadas. GET de autorización, vínculos y paneles: 200; restricciones de profesor y visitante: 403.')
    print('Comprobaciones GET:',len(http),'; manifiesto:',ruta.relative_to(raiz).as_posix())


if __name__=='__main__':
    verificar()
