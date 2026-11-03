from django.db import migrations


SQL = r"""
CREATE FUNCTION public.zdb_e3_inmutable() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog AS $$ BEGIN
 RAISE EXCEPTION 'Fuente o evento inmutable' USING ERRCODE='23514';
END $$;

CREATE FUNCTION public.zdb_e3_version() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog AS $$
DECLARE anterior jsonb; siguiente jsonb; excepciones text[];
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Se conserva la historia editorial' USING ERRCODE='23514'; END IF;
 IF TG_OP='UPDATE' THEN
  IF OLD.estado IN ('aprobado','retirado') AND NEW.estado NOT IN ('aprobado','retirado') THEN
   RAISE EXCEPTION 'No se reabre una edición publicada' USING ERRCODE='23514'; END IF;
  IF OLD.estado='retirado' AND NEW.estado<>'retirado' THEN
   RAISE EXCEPTION 'Retiro irreversible; crear otra edición' USING ERRCODE='23514'; END IF;
  IF OLD.estado<>'borrador' OR coalesce((to_jsonb(OLD)->>'original_cerrado')::boolean,false) THEN
   excepciones:=ARRAY['estado','revision','vigente','observaciones_revision'];
   IF OLD.estado='en_revision' THEN excepciones:=excepciones||ARRAY['revisor_id','revisada_en']; END IF;
   anterior:=to_jsonb(OLD)-excepciones; siguiente:=to_jsonb(NEW)-excepciones;
   IF anterior IS DISTINCT FROM siguiente THEN
    RAISE EXCEPTION 'Contenido editorial congelado' USING ERRCODE='23514'; END IF;
  END IF;
 END IF;
 IF NEW.estado NOT IN ('borrador','en_revision','aprobado','retirado') OR NEW.naturaleza NOT IN ('original_institucional','propuesta_revisada','adaptacion_docente') THEN
  RAISE EXCEPTION 'Estado o naturaleza inválidos' USING ERRCODE='23514'; END IF;
 IF NEW.estado='aprobado' AND (NEW.revisor_id IS NULL OR NEW.revisada_en IS NULL) THEN
  RAISE EXCEPTION 'Publicación requiere revisión' USING ERRCODE='23514'; END IF;
 IF NEW.estado='aprobado' AND (TG_OP='INSERT' OR OLD.estado<>'aprobado') AND
  NOT public.zdb_tiene_rol(NEW.revisor_id,'coordinador') THEN
  RAISE EXCEPTION 'Revisión reservada a coordinación vigente' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;

CREATE FUNCTION public.zdb_e3_destino(tabla text, dato jsonb) RETURNS TABLE(tipo text, vid bigint)
LANGUAGE plpgsql SET search_path=pg_catalog AS $$ BEGIN
 IF tabla IN ('curriculo_fasecurricular','curriculo_semanacurricular','curriculo_elementocurricular') THEN
  RETURN QUERY SELECT 'curriculo_mallaversion'::text,(dato->>'version_id')::bigint;
 ELSIF tabla='curriculo_claseprevista' THEN
  RETURN QUERY SELECT 'curriculo_mallaversion'::text,s.version_id FROM public.curriculo_semanacurricular s WHERE s.id=(dato->>'semana_id')::bigint;
 ELSIF tabla IN ('curriculo_procedenciacurricular','curriculo_actividadcurricular','curriculo_ubicacioncurricular') THEN
  RETURN QUERY SELECT 'curriculo_mallaversion'::text,e.version_id FROM public.curriculo_elementocurricular e WHERE e.id=(dato->>'elemento_id')::bigint;
 ELSIF tabla LIKE 'biblioteca_ejercicioversion_%' THEN
  RETURN QUERY SELECT 'biblioteca_ejercicioversion'::text,(dato->>'ejercicioversion_id')::bigint;
 ELSIF tabla LIKE 'biblioteca_materialdocenteversion_%' THEN
  RETURN QUERY SELECT 'biblioteca_materialdocenteversion'::text,(dato->>'materialdocenteversion_id')::bigint;
 ELSE
  RETURN QUERY SELECT 'biblioteca_ejercicioversion'::text,(dato->>'version_id')::bigint;
 END IF;
END $$;

CREATE FUNCTION public.zdb_e3_hijo() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog AS $$
DECLARE d jsonb; objetivo record; estado text; cerrado boolean; esperado bigint; otro bigint;
BEGIN
 FOR d IN SELECT CASE WHEN TG_OP='INSERT' THEN NULL ELSE to_jsonb(OLD) END
          UNION ALL SELECT CASE WHEN TG_OP='DELETE' THEN NULL ELSE to_jsonb(NEW) END LOOP
  IF d IS NULL THEN CONTINUE; END IF;
  FOR objetivo IN SELECT * FROM public.zdb_e3_destino(TG_TABLE_NAME,d) LOOP
   EXECUTE format('SELECT estado,coalesce((to_jsonb(v)->>''original_cerrado'')::boolean,false) FROM public.%I v WHERE id=$1 FOR UPDATE',objetivo.tipo)
     INTO estado,cerrado USING objetivo.vid;
   IF estado IS DISTINCT FROM 'borrador' OR cerrado THEN
    RAISE EXCEPTION 'Hijo de contenido congelado' USING ERRCODE='23514'; END IF;
  END LOOP;
 END LOOP;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 IF TG_TABLE_NAME='curriculo_semanacurricular' THEN
  SELECT f.version_id INTO esperado FROM public.curriculo_fasecurricular f WHERE f.id=NEW.fase_id;
  IF esperado IS DISTINCT FROM NEW.version_id THEN RAISE EXCEPTION 'Fase de otra versión' USING ERRCODE='23514'; END IF;
 ELSIF TG_TABLE_NAME IN ('curriculo_elementocurricular','curriculo_ubicacioncurricular') THEN
  IF TG_TABLE_NAME='curriculo_ubicacioncurricular' THEN
   SELECT e.version_id INTO otro FROM public.curriculo_elementocurricular e WHERE e.id=NEW.elemento_id;
  ELSE otro:=NEW.version_id; END IF;
  IF NEW.fase_id IS NOT NULL THEN SELECT f.version_id INTO esperado FROM public.curriculo_fasecurricular f WHERE f.id=NEW.fase_id;
  ELSIF NEW.semana_id IS NOT NULL THEN SELECT s.version_id INTO esperado FROM public.curriculo_semanacurricular s WHERE s.id=NEW.semana_id;
  ELSIF NEW.clase_id IS NOT NULL THEN SELECT s.version_id INTO esperado FROM public.curriculo_claseprevista c JOIN public.curriculo_semanacurricular s ON s.id=c.semana_id WHERE c.id=NEW.clase_id;
  ELSE esperado:=otro; END IF;
  IF esperado IS DISTINCT FROM otro THEN RAISE EXCEPTION 'Alcance de otra versión' USING ERRCODE='23514'; END IF;
  IF (to_jsonb(NEW)->>'padre_id') IS NOT NULL THEN
   SELECT e.version_id INTO esperado FROM public.curriculo_elementocurricular e WHERE e.id=NEW.padre_id;
   IF esperado IS DISTINCT FROM otro THEN RAISE EXCEPTION 'Padre de otra versión' USING ERRCODE='23514'; END IF;
   IF EXISTS(WITH RECURSIVE ancestros AS (
    SELECT e.id,e.padre_id FROM public.curriculo_elementocurricular e WHERE e.id=NEW.padre_id
    UNION SELECT e.id,e.padre_id FROM public.curriculo_elementocurricular e JOIN ancestros a ON e.id=a.padre_id)
    SELECT 1 FROM ancestros WHERE id=NEW.id) OR NEW.padre_id=NEW.id THEN
     RAISE EXCEPTION 'Ciclo curricular' USING ERRCODE='23514'; END IF;
  END IF;
 ELSIF TG_TABLE_NAME='curriculo_claseprevista' THEN
  IF EXISTS(SELECT 1 FROM public.curriculo_claseprevista c JOIN public.curriculo_semanacurricular s ON s.id=c.semana_id
    WHERE s.version_id=(SELECT version_id FROM public.curriculo_semanacurricular WHERE id=NEW.semana_id)
    AND c.ordinal=NEW.ordinal AND c.id<>NEW.id) THEN RAISE EXCEPTION 'Clase global duplicada' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NEW;
END $$;
"""

FUENTES = ['recursos_archivoprivado', 'recursos_fuentedocumento', 'recursos_fuenteversion', 'recursos_fragmentofuente', 'curriculo_eventomalla', 'biblioteca_eventoejercicio', 'biblioteca_eventomaterial']
VERSIONES = ['curriculo_mallaversion', 'biblioteca_ejercicioversion', 'biblioteca_materialdocenteversion']
HIJOS = ['curriculo_fasecurricular', 'curriculo_semanacurricular', 'curriculo_claseprevista', 'curriculo_elementocurricular', 'curriculo_procedenciacurricular', 'curriculo_actividadcurricular', 'curriculo_ubicacioncurricular', 'biblioteca_pasoejercicio', 'biblioteca_adaptacionejercicio', 'biblioteca_exigenciaejercicio', 'biblioteca_procedenciaejercicio', 'biblioteca_materialejercicio', 'biblioteca_ejercicioversion_programas', 'biblioteca_ejercicioversion_etiquetas', 'biblioteca_materialdocenteversion_programas']


def instalar(apps, editor):
    if editor.connection.vendor != 'postgresql':
        raise RuntimeError('La integridad de Etapa 3 exige PostgreSQL aislado.')
    editor.execute(SQL, params=None)
    for tabla in FUENTES:
        editor.execute(f'CREATE TRIGGER zdb_e3_inmutable BEFORE UPDATE OR DELETE ON public.{tabla} FOR EACH ROW EXECUTE FUNCTION public.zdb_e3_inmutable()')
    for tabla in VERSIONES:
        editor.execute(f'CREATE TRIGGER zdb_e3_version BEFORE INSERT OR UPDATE OR DELETE ON public.{tabla} FOR EACH ROW EXECUTE FUNCTION public.zdb_e3_version()')
    for tabla in HIJOS:
        editor.execute(f'CREATE TRIGGER zdb_e3_hijo BEFORE INSERT OR UPDATE OR DELETE ON public.{tabla} FOR EACH ROW EXECUTE FUNCTION public.zdb_e3_hijo()')


def retirar(apps, editor):
    if any(apps.get_model(app, modelo).objects.exists() for app, modelo in [('curriculo','MallaVersion'), ('biblioteca','EjercicioVersion'), ('biblioteca','MaterialDocenteVersion')]):
        raise RuntimeError('No retirar integridad con contenido existente; restaurar copia o conciliar historia.')
    for lista, trigger in [(FUENTES,'inmutable'),(VERSIONES,'version'),(HIJOS,'hijo')]:
        for tabla in lista: editor.execute(f'DROP TRIGGER zdb_e3_{trigger} ON public.{tabla}')
    for nombre in ['hijo()', 'destino(text,jsonb)', 'version()', 'inmutable()']:
        editor.execute('DROP FUNCTION public.zdb_e3_'+nombre)


class Migration(migrations.Migration):
    dependencies = [('recursos','0001_initial'), ('biblioteca','0002_initial'), ('curriculo','0002_ubicacioncurricular'), ('cuentas','0007_remove_pertenenciarol_pertenencia_estado_coherente_and_more')]
    operations = [migrations.RunPython(instalar, retirar)]
