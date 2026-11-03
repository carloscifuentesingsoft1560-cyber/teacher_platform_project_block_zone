"""Extiende las garantías históricas sin reescribir migraciones aplicadas."""
from importlib import import_module
import re
from django.db import migrations

anterior = import_module('inscripciones.migrations.0004_ejecucion_administrativa')
sql_b1 = next(o.sql for o in import_module('inscripciones.migrations.0002_progresioninstitucional_eventoprogresion_and_more').Migration.operations
             if isinstance(o,migrations.RunSQL) and 'CREATE FUNCTION public.zdb_validar_ascenso_b1' in o.sql)
validar_anterior = re.search(r'CREATE FUNCTION public.zdb_validar_ascenso_b1\(\).*?END \$\$;', sql_b1, re.S).group(0).replace('CREATE FUNCTION','CREATE OR REPLACE FUNCTION',1)
validar = validar_anterior.replace("u.rol='coordinador' AND u.is_active", "public.zdb_tiene_rol(u.id,'coordinador')")
validar = validar.replace("SELECT count(*) FROM public.cuentas_usuario WHERE rol='coordinador' AND is_active", "SELECT count(*) FROM public.cuentas_pertenenciarol WHERE rol='coordinador' AND vigente")
guardia = anterior.GUARDIA.replace("rol IN ('administrador','coordinador')", "public.zdb_tiene_rol(id,'administrador')")


class Migration(migrations.Migration):
    dependencies = [('cuentas','0006_roles_compatibilidad'), ('inscripciones','0004_ejecucion_administrativa')]
    operations = [migrations.RunSQL(validar+'\n'+guardia, reverse_sql=validar_anterior+'\n'+anterior.GUARDIA)]
