"""Guardias B2.2 aditivas. Irreversible: no dejar historial sin sus protecciones.

0004 sin 0005 no es una instalación habilitada; desplegar ambas como una unidad.
No altera funciones, triggers ni tablas de B1, B2.1 o sesiones.
"""
from django.db import migrations


SQL = r"""
CREATE FUNCTION public.zdb_b22_contexto(cid bigint) RETURNS jsonb
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE c public.biblioteca_correspondenciafuncional; resultado jsonb;
BEGIN
 SELECT * INTO c FROM public.biblioteca_correspondenciafuncional WHERE id=cid;
 IF c.ejercicio_id IS NOT NULL THEN
  SELECT jsonb_build_object('tipo','ejercicio','contenido',to_jsonb(e)) INTO resultado
   FROM public.biblioteca_ejercicioversion e WHERE e.id=c.ejercicio_id;
 ELSIF c.tarea_id IS NOT NULL THEN
  SELECT jsonb_build_object('tipo','tarea','contenido',to_jsonb(t),'plan',to_jsonb(p)) INTO resultado
   FROM public.sesiones_tareasesion t JOIN public.sesiones_plansesion p ON p.id=t.plan_id WHERE t.id=c.tarea_id;
 ELSE
  SELECT jsonb_build_object('tipo','actividad','contenido',to_jsonb(a),'tarea',to_jsonb(t),'ejecucion',to_jsonb(e)) INTO resultado
   FROM public.sesiones_actividadejecutada a JOIN public.sesiones_tareasesion t ON t.id=a.tarea_id
   JOIN public.sesiones_ejecucionsesion e ON e.id=a.ejecucion_id WHERE a.id=c.actividad_id;
 END IF;
 IF resultado IS NULL THEN RAISE EXCEPTION 'Destino funcional inexistente' USING ERRCODE='23514'; END IF;
 RETURN resultado;
END $$;

CREATE FUNCTION public.zdb_b22_destino(cid bigint) RETURNS bigint
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE c public.biblioteca_correspondenciafuncional; d bigint; valido boolean;
BEGIN
 SELECT * INTO c FROM public.biblioteca_correspondenciafuncional WHERE id=cid FOR UPDATE;
 IF c.ejercicio_id IS NOT NULL THEN
  PERFORM 1 FROM public.biblioteca_ejercicioversion WHERE id=c.ejercicio_id FOR UPDATE;
  SELECT disciplina_id,estado='aprobado' INTO d,valido FROM public.biblioteca_ejercicioversion WHERE id=c.ejercicio_id;
 ELSIF c.tarea_id IS NOT NULL THEN
  PERFORM 1 FROM public.sesiones_plansesion WHERE id=(SELECT plan_id FROM public.sesiones_tareasesion WHERE id=c.tarea_id) FOR UPDATE;
  SELECT g.disciplina_id,p.sellado INTO d,valido FROM public.sesiones_tareasesion t
   JOIN public.sesiones_plansesion p ON p.id=t.plan_id JOIN public.sesiones_sesion s ON s.id=p.sesion_id
   JOIN public.organizacion_grupo g ON g.id=s.grupo_id WHERE t.id=c.tarea_id;
 ELSE
  PERFORM 1 FROM public.sesiones_ejecucionsesion WHERE id=(SELECT ejecucion_id FROM public.sesiones_actividadejecutada WHERE id=c.actividad_id) FOR UPDATE;
  SELECT g.disciplina_id,(e.finalizada_en IS NOT NULL AND p.sellado AND t.plan_id=e.plan_id AND a.resultado<>'omitida')
   INTO d,valido FROM public.sesiones_actividadejecutada a
   JOIN public.sesiones_ejecucionsesion e ON e.id=a.ejecucion_id
   JOIN public.sesiones_tareasesion t ON t.id=a.tarea_id JOIN public.sesiones_plansesion p ON p.id=e.plan_id
   JOIN public.sesiones_sesion s ON s.id=e.sesion_id JOIN public.organizacion_grupo g ON g.id=s.grupo_id WHERE a.id=c.actividad_id;
 END IF;
 IF d IS NULL OR valido IS DISTINCT FROM true THEN
  RAISE EXCEPTION 'Destino no estable, no publicado u omitido' USING ERRCODE='23514';
 END IF;
 RETURN d;
END $$;

CREATE FUNCTION public.zdb_b22_guardia() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE j jsonb; padre bigint; ultimo jsonb; tabla text; campo text; d bigint;
 v public.biblioteca_perfilfuncionalversion; ep public.biblioteca_eventoperfilfuncional;
 c public.biblioteca_correspondenciafuncional; t public.biblioteca_terminoactividad;
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Historial funcional inmutable' USING ERRCODE='23514'; END IF;
 -- Orden global compartido con roles, identidades y B1/B2.1.
 PERFORM id FROM public.cuentas_usuario ORDER BY id FOR UPDATE;
 j:=to_jsonb(NEW);
 IF j ? 'creada_en' THEN NEW.creada_en:=clock_timestamp(); END IF;
 IF j ? 'registrada_en' THEN NEW.registrada_en:=clock_timestamp(); END IF;

 IF TG_TABLE_NAME='biblioteca_perfilfuncionalversion' OR TG_TABLE_NAME='biblioteca_correspondenciafuncionalversion' THEN
  IF TG_TABLE_NAME='biblioteca_perfilfuncionalversion' THEN
   padre:=NEW.perfil_id; campo:='perfil_id'; tabla:='biblioteca_perfilfuncional';
  ELSE
   padre:=NEW.correspondencia_id; campo:='correspondencia_id'; tabla:='biblioteca_correspondenciafuncional';
  END IF;
  EXECUTE format('SELECT id FROM public.%I WHERE id=$1 FOR UPDATE',tabla) USING padre;
  EXECUTE format('SELECT to_jsonb(x) FROM public.%I x WHERE %I=$1 ORDER BY numero DESC LIMIT 1',TG_TABLE_NAME,campo) INTO ultimo USING padre;
  IF (ultimo IS NULL AND (NEW.numero<>1 OR NEW.anterior_id IS NOT NULL)) OR
   (ultimo IS NOT NULL AND (NEW.numero<>(ultimo->>'numero')::integer+1 OR NEW.anterior_id IS DISTINCT FROM (ultimo->>'id')::bigint)) THEN
   RAISE EXCEPTION 'Versión funcional no consecutiva' USING ERRCODE='23514';
  END IF;
  IF ultimo IS NOT NULL THEN
   tabla:=CASE WHEN campo='perfil_id' THEN 'biblioteca_eventoperfilfuncional' ELSE 'biblioteca_eventocorrespondenciafuncional' END;
   EXECUTE format('SELECT to_jsonb(x) FROM public.%I x WHERE version_id=$1 ORDER BY numero DESC LIMIT 1',tabla) INTO ultimo USING (ultimo->>'id')::bigint;
   IF ultimo IS NULL OR ultimo->>'accion'='retiro' THEN RAISE EXCEPTION 'Cadena retirada o incompleta' USING ERRCODE='23514'; END IF;
  END IF;
  IF campo='correspondencia_id' THEN
   SELECT * INTO v FROM public.biblioteca_perfilfuncionalversion WHERE id=NEW.perfil_version_id FOR UPDATE;
   SELECT * INTO ep FROM public.biblioteca_eventoperfilfuncional WHERE version_id=v.id ORDER BY numero DESC LIMIT 1;
   IF v.id IS NULL OR ep.id IS NULL OR ep.id IS DISTINCT FROM NEW.evento_perfil_id OR ep.accion='retiro'
    OR EXISTS(SELECT 1 FROM public.biblioteca_perfilfuncionalversion WHERE perfil_id=v.perfil_id AND numero>v.numero) THEN
    RAISE EXCEPTION 'Perfil retirado, sustituido o referencia de revisión obsoleta' USING ERRCODE='23514';
   END IF;
   SELECT disciplina_id INTO d FROM public.biblioteca_perfilfuncional WHERE id=v.perfil_id;
   IF d IS DISTINCT FROM public.zdb_b22_destino(NEW.correspondencia_id)
    OR NEW.contexto IS DISTINCT FROM public.zdb_b22_contexto(NEW.correspondencia_id) THEN
    RAISE EXCEPTION 'Disciplina o contexto exacto incompatible' USING ERRCODE='23514'; END IF;
   IF NEW.adaptacion_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM public.biblioteca_adaptacionperfilfuncional WHERE id=NEW.adaptacion_id AND version_id=v.id) THEN
    RAISE EXCEPTION 'Adaptación ajena al perfil' USING ERRCODE='23514'; END IF;
   SELECT * INTO c FROM public.biblioteca_correspondenciafuncional WHERE id=NEW.correspondencia_id;
   IF c.actividad_id IS NOT NULL AND EXISTS(SELECT 1 FROM public.sesiones_actividadejecutada WHERE id=c.actividad_id AND resultado='modificada') AND NEW.adaptacion_id IS NULL THEN
    RAISE EXCEPTION 'Actividad modificada exige adaptación explícita' USING ERRCODE='23514'; END IF;
  END IF;

 ELSIF TG_TABLE_NAME IN ('biblioteca_exigenciaperfilfuncional','biblioteca_condicionperfilfuncional','biblioteca_adaptacionperfilfuncional','biblioteca_procedenciaperfilfuncional') THEN
  PERFORM id FROM public.biblioteca_perfilfuncionalversion WHERE id=NEW.version_id FOR UPDATE;
  IF EXISTS(SELECT 1 FROM public.biblioteca_eventoperfilfuncional WHERE version_id=NEW.version_id) THEN
   RAISE EXCEPTION 'Detalle de perfil ya sellado por su primer evento' USING ERRCODE='23514'; END IF;
  IF TG_TABLE_NAME='biblioteca_exigenciaperfilfuncional' THEN
   SELECT * INTO t FROM public.biblioteca_terminoactividad WHERE id=NEW.termino_id FOR UPDATE;
   IF t.id IS NULL OR t.namespace<>'exigencia_funcional' OR NEW.codigo_historico IS DISTINCT FROM t.codigo OR NEW.nombre_historico IS DISTINCT FROM t.nombre THEN
    RAISE EXCEPTION 'Término funcional o instantánea incompatible' USING ERRCODE='23514'; END IF;
  ELSIF TG_TABLE_NAME='biblioteca_condicionperfilfuncional' THEN
   IF NOT EXISTS(SELECT 1 FROM public.biblioteca_exigenciaperfilfuncional WHERE id=NEW.exigencia_id AND version_id=NEW.version_id) THEN
    RAISE EXCEPTION 'Condición ajena al perfil' USING ERRCODE='23514'; END IF;
  ELSIF TG_TABLE_NAME='biblioteca_adaptacionperfilfuncional' THEN
   IF NOT EXISTS(SELECT 1 FROM public.biblioteca_condicionperfilfuncional WHERE id=NEW.condicion_id AND version_id=NEW.version_id) THEN
    RAISE EXCEPTION 'Adaptación ajena al perfil' USING ERRCODE='23514'; END IF;
  END IF;

 ELSIF TG_TABLE_NAME IN ('biblioteca_eventoperfilfuncional','biblioteca_eventocorrespondenciafuncional') THEN
  tabla:=CASE WHEN TG_TABLE_NAME='biblioteca_eventoperfilfuncional' THEN 'biblioteca_perfilfuncionalversion' ELSE 'biblioteca_correspondenciafuncionalversion' END;
  EXECUTE format('SELECT id FROM public.%I WHERE id=$1 FOR UPDATE',tabla) USING NEW.version_id;
  EXECUTE format('SELECT to_jsonb(x) FROM public.%I x WHERE version_id=$1 ORDER BY numero DESC LIMIT 1',TG_TABLE_NAME) INTO ultimo USING NEW.version_id;
  IF (ultimo IS NULL AND (NEW.numero<>1 OR NEW.accion<>'propuesta' OR NEW.anterior_id IS NOT NULL)) OR
   (ultimo IS NOT NULL AND (ultimo->>'accion'='retiro' OR NEW.numero<>(ultimo->>'numero')::integer+1 OR NEW.anterior_id IS DISTINCT FROM (ultimo->>'id')::bigint OR NEW.accion NOT IN ('revision','retiro'))) THEN
   RAISE EXCEPTION 'Evento no consecutivo o retiro terminal' USING ERRCODE='23514'; END IF;
  IF NOT public.zdb_tiene_rol(NEW.actor_id,'administrador') THEN
   RAISE EXCEPTION 'Registro documental exige administración; no es competencia funcional' USING ERRCODE='23514'; END IF;
  PERFORM public.zdb_b21_identidad(NEW.enlace_actor_id,NEW.actor_id,NEW.persona_actor_id,NEW.version_enlace_actor,NEW.evidencia_actor);
  tabla:=CASE WHEN TG_TABLE_NAME='biblioteca_eventoperfilfuncional' THEN 'biblioteca_eventocorrespondenciafuncional' ELSE 'biblioteca_eventoperfilfuncional' END;
  EXECUTE format('SELECT to_jsonb(x) FROM public.%I x WHERE actor_id=$1 AND clave=$2',tabla) INTO j USING NEW.actor_id,NEW.clave;
  IF j IS NOT NULL THEN RAISE EXCEPTION 'Clave documental ya utilizada' USING ERRCODE='23514'; END IF;
  IF TG_TABLE_NAME='biblioteca_eventocorrespondenciafuncional' AND NEW.accion<>'retiro' THEN
   SELECT e.* INTO ep FROM public.biblioteca_correspondenciafuncionalversion cv
    JOIN public.biblioteca_eventoperfilfuncional e ON e.id=cv.evento_perfil_id WHERE cv.id=NEW.version_id;
   IF ep.id IS NULL OR EXISTS(SELECT 1 FROM public.biblioteca_eventoperfilfuncional WHERE version_id=ep.version_id AND numero>ep.numero)
    OR EXISTS(SELECT 1 FROM public.biblioteca_perfilfuncionalversion pv JOIN public.biblioteca_perfilfuncionalversion origen ON origen.id=ep.version_id WHERE pv.perfil_id=origen.perfil_id AND pv.numero>origen.numero) THEN
    RAISE EXCEPTION 'Fundamento documental cambiado; requiere nueva versión' USING ERRCODE='23514'; END IF;
  END IF;
 END IF;
 RETURN NEW;
END $$;

CREATE FUNCTION public.zdb_b22_completo() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE tabla text; campo text; existe boolean;
BEGIN
 IF TG_TABLE_NAME='biblioteca_perfilfuncional' THEN tabla:='biblioteca_perfilfuncionalversion'; campo:='perfil_id';
 ELSIF TG_TABLE_NAME='biblioteca_correspondenciafuncional' THEN tabla:='biblioteca_correspondenciafuncionalversion'; campo:='correspondencia_id';
 ELSIF TG_TABLE_NAME='biblioteca_perfilfuncionalversion' THEN tabla:='biblioteca_eventoperfilfuncional'; campo:='version_id';
 ELSE tabla:='biblioteca_eventocorrespondenciafuncional'; campo:='version_id'; END IF;
 EXECUTE format('SELECT EXISTS(SELECT 1 FROM public.%I WHERE %I=$1 AND numero=1)',tabla,campo) INTO existe USING NEW.id;
 IF NOT existe THEN RAISE EXCEPTION 'Primer evento o primera versión obligatorios' USING ERRCODE='23514'; END IF;
 IF TG_TABLE_NAME='biblioteca_perfilfuncionalversion' AND (
  NOT EXISTS(SELECT 1 FROM public.biblioteca_exigenciaperfilfuncional WHERE version_id=NEW.id) OR
  NOT EXISTS(SELECT 1 FROM public.biblioteca_procedenciaperfilfuncional WHERE version_id=NEW.id)) THEN
  RAISE EXCEPTION 'Perfil exige declaración de exigencias y procedencia' USING ERRCODE='23514'; END IF;
 RETURN NULL;
END $$;
"""

TABLAS = ('perfilfuncional', 'perfilfuncionalversion', 'exigenciaperfilfuncional',
          'condicionperfilfuncional', 'adaptacionperfilfuncional', 'procedenciaperfilfuncional',
          'eventoperfilfuncional', 'correspondenciafuncional', 'correspondenciafuncionalversion',
          'eventocorrespondenciafuncional')
for tabla in TABLAS:
    SQL += f'\nCREATE TRIGGER zdb_b22_guardia BEFORE INSERT OR UPDATE OR DELETE ON public.biblioteca_{tabla} FOR EACH ROW EXECUTE FUNCTION public.zdb_b22_guardia();\n'
for tabla in ('perfilfuncional', 'perfilfuncionalversion', 'correspondenciafuncional', 'correspondenciafuncionalversion'):
    SQL += f'\nCREATE CONSTRAINT TRIGGER zdb_b22_completo AFTER INSERT ON public.biblioteca_{tabla} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.zdb_b22_completo();\n'


class Migration(migrations.Migration):
    dependencies = [('biblioteca', '0004_catalogo_funcional_b2_2'),
                    ('cuentas', '0011_guardias_mandatos_acreditaciones_b2_1')]
    operations = [migrations.RunSQL(SQL)]
