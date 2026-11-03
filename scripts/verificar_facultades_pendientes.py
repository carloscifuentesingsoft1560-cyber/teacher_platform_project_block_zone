"""Verificación de solo lectura anterior a aprobar la migración de facultades.

Ejecutar con django_local.py shell / runpy. No modifica datos ni manifiestos.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
from django.db import connection,transaction
from django.db.migrations.executor import MigrationExecutor
from rest_framework.test import APIClient
from cuentas.models import Usuario


def exigir(condicion, mensaje):
    if not condicion:
        raise RuntimeError(mensaje)


def verificar():
    raiz=Path(__file__).resolve().parent.parent
    referencia=sorted((raiz/'respaldos').glob('facultades_antes_*.json'))[-1]
    esperado=json.loads(referencia.read_text(encoding='utf-8'))
    with transaction.atomic():
        with connection.cursor() as c:
            c.execute('SET TRANSACTION READ ONLY')
            c.execute('SELECT current_database(),current_schema()')
            exigir(connection.vendor=='postgresql' and connection.settings_dict['NAME']=='zona_bloque' and c.fetchone()==('zona_bloque','public'),'Destino no autorizado.')
            tablas=connection.introspection.table_names()
            actuales={}
            for t in tablas:
                c.execute('SELECT row_to_json(t)::text FROM '+connection.ops.quote_name(t)+' t')
                filas=sorted(x[0] for x in c.fetchall())
                actuales[t]={'filas':len(filas),'sha256':hashlib.sha256(json.dumps(filas,ensure_ascii=False).encode()).hexdigest()}
            exigir(actuales==esperado['tablas'],'Los registros cambiaron respecto a la referencia; revisar sin alterar datos.')
            c.execute('SELECT facultad_para_autorizar FROM deportistas_vinculoacudiente WHERE id=3')
            exigir(c.fetchone()==('pendiente',),'El vínculo 3 no coincide con el estado previo.')
            exigir('deportistas_comprobacionfacultad' not in tablas,'La tabla nueva ya existe.')
            exigir('comprobacion_facultad_id' not in {f.name for f in connection.introspection.get_table_description(c,'deportistas_autorizacion')},'El campo nuevo ya existe.')
            c.execute('SELECT COUNT(*) FROM pg_proc WHERE proname=%s',['zdb_facultad_historial_inmutable'])
            exigir(c.fetchone()[0]==0,'Colisión de función.')
            c.execute('SELECT COUNT(*) FROM pg_trigger WHERE tgname=%s',['zdb_facultad_no_modificar'])
            exigir(c.fetchone()[0]==0,'Colisión de trigger.')
        e=MigrationExecutor(connection);e.loader.check_consistent_history(connection)
        plan=e.migration_plan(e.loader.graph.leaf_nodes())
        exigir([(m.app_label,m.name,b) for m,b in plan]==[('deportistas','0003_comprobacion_facultades',False)],'Plan distinto de la única migración propuesta.')
        print('Base efectiva: zona_bloque/public. Tablas idénticas por conteos y SHA-256:',len(actuales),'; vínculo 3 pendiente.')
        print('Pendiente exclusivamente deportistas.0003_comprobacion_facultades; operaciones:',dict(Counter(type(o).__name__ for o in plan[0][0].operations)))
        print('Sin campo, tabla, función o trigger nuevos en PostgreSQL real.')
        for rol in ('administrador','coordinador'):
            actor=Usuario.objects.filter(rol=rol,is_active=True).first()
            exigir(actor is not None,'Falta actor autorizado para consulta de panel.')
            cli=APIClient(HTTP_HOST='localhost');cli.force_authenticate(actor)
            for url,codigo in [('/api/acudientes/',200),('/api/vinculos-acudientes/?deportista=9',200),('/api/autorizaciones/',503),('/api/paneles/'+rol+'/resumen/',200)]:
                estado=cli.get(url).status_code
                exigir(estado==codigo,'Respuesta GET inesperada.')
                print('GET',rol,url,estado)
    print('SHA-256 de migración:',hashlib.sha256((raiz/'backend/deportistas/migrations/0003_comprobacion_facultades.py').read_bytes()).hexdigest())


if __name__=='__main__':
    verificar()
