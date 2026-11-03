from django.db import migrations

SQL = r"""
CREATE FUNCTION public.zdb_e3_identidad() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog AS $$ BEGIN
 RAISE EXCEPTION 'Identidad estable; crear una edición para cambiar contenido' USING ERRCODE='23514';
END $$;
CREATE TRIGGER zdb_e3_identidad BEFORE UPDATE OR DELETE ON public.curriculo_malla FOR EACH ROW EXECUTE FUNCTION public.zdb_e3_identidad();
CREATE TRIGGER zdb_e3_identidad BEFORE UPDATE OR DELETE ON public.biblioteca_ejercicio FOR EACH ROW EXECUTE FUNCTION public.zdb_e3_identidad();
CREATE TRIGGER zdb_e3_identidad BEFORE UPDATE OR DELETE ON public.biblioteca_materialdocente FOR EACH ROW EXECUTE FUNCTION public.zdb_e3_identidad();
CREATE TRIGGER zdb_e3_identidad BEFORE UPDATE OR DELETE ON public.biblioteca_terminoactividad FOR EACH ROW EXECUTE FUNCTION public.zdb_e3_identidad();
"""
REVERSE = '\n'.join('DROP TRIGGER zdb_e3_identidad ON public.'+t+';' for t in ['curriculo_malla','biblioteca_ejercicio','biblioteca_materialdocente','biblioteca_terminoactividad'])+'\nDROP FUNCTION public.zdb_e3_identidad();'

class Migration(migrations.Migration):
    dependencies = [('recursos','0002_integridad_editorial')]
    operations = [migrations.RunSQL(SQL, REVERSE)]
