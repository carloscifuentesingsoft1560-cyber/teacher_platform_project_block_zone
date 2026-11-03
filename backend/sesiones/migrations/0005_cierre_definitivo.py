from django.db import migrations, models
import django.db.models.deletion

SQL = r"""
CREATE FUNCTION public.zdb_asistencia_guardia() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE cerrada boolean; s public.sesiones_sesion; i public.inscripciones_inscripcion;
BEGIN
 IF TG_OP='INSERT' THEN
  SELECT * INTO s FROM public.sesiones_sesion WHERE id=NEW.sesion_id FOR UPDATE;
  SELECT * INTO i FROM public.inscripciones_inscripcion WHERE id=NEW.inscripcion_id;
  IF s.asistencia_confirmada OR i.grupo_id<>s.grupo_id OR i.deportista_id<>NEW.deportista_id OR i.fecha_ingreso>s.fecha OR (i.fecha_salida IS NOT NULL AND i.fecha_salida<=s.fecha) THEN
   RAISE EXCEPTION 'Participante no elegible o padrón cerrado' USING ERRCODE='23514'; END IF;
 ELSE
  SELECT asistencia_confirmada INTO cerrada FROM public.sesiones_sesion WHERE id=OLD.sesion_id FOR UPDATE;
  IF TG_OP='UPDATE' AND (NEW.sesion_id<>OLD.sesion_id OR NEW.inscripcion_id<>OLD.inscripcion_id OR NEW.deportista_id<>OLD.deportista_id) THEN
   RAISE EXCEPTION 'Identidad de asistencia inmutable' USING ERRCODE='23514'; END IF;
  IF cerrada THEN
   IF TG_OP='UPDATE' AND pg_trigger_depth()=2 AND EXISTS (
    SELECT 1 FROM public.sesiones_correccionasistencia c WHERE c.asistencia_id=OLD.id AND c.anterior=OLD.estado AND c.nuevo=NEW.estado
   ) THEN RETURN NEW; END IF;
   RAISE EXCEPTION 'Asistencia cerrada; requiere corrección administrativa' USING ERRCODE='23514';
  END IF;
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER zdb_asistencia_guardia BEFORE INSERT OR UPDATE OR DELETE ON public.sesiones_asistencia FOR EACH ROW EXECUTE FUNCTION public.zdb_asistencia_guardia();

CREATE FUNCTION public.zdb_sesion_cierre_guardia() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
BEGIN
 IF TG_OP='INSERT' THEN
  IF NEW.estado='realizada' THEN RAISE EXCEPTION 'Validación funcional institucional pendiente' USING ERRCODE='23514'; END IF;
  RETURN NEW;
 END IF;
 IF OLD.asistencia_confirmada AND NOT NEW.asistencia_confirmada THEN RAISE EXCEPTION 'No se reabre asistencia cerrada' USING ERRCODE='23514'; END IF;
 IF OLD.asistencia_confirmada OR EXISTS (SELECT 1 FROM public.sesiones_ejecucionsesion WHERE sesion_id=OLD.id AND finalizada_en IS NOT NULL) THEN
  IF ROW(NEW.grupo_id,NEW.profesor_id,NEW.fecha,NEW.hora_inicio,NEW.hora_fin) IS DISTINCT FROM ROW(OLD.grupo_id,OLD.profesor_id,OLD.fecha,OLD.hora_inicio,OLD.hora_fin) THEN
   RAISE EXCEPTION 'Contexto de sesión cerrado e inmutable' USING ERRCODE='23514'; END IF;
 END IF;
 IF NEW.estado='realizada' AND OLD.estado<>'realizada' THEN RAISE EXCEPTION 'Validación funcional institucional pendiente' USING ERRCODE='23514'; END IF;
 IF OLD.estado='realizada' AND ROW(NEW.estado,NEW.plan_ejecutado_id,NEW.inicio_real,NEW.fin_real) IS DISTINCT FROM ROW(OLD.estado,OLD.plan_ejecutado_id,OLD.inicio_real,OLD.fin_real) THEN
  RAISE EXCEPTION 'Ejecución validada inmutable' USING ERRCODE='23514'; END IF;
 IF NEW.asistencia_confirmada AND NOT OLD.asistencia_confirmada THEN
  IF NEW.fecha>(statement_timestamp() AT TIME ZONE 'America/Bogota')::date THEN RAISE EXCEPTION 'No se cierra asistencia futura' USING ERRCODE='23514'; END IF;
  IF EXISTS (SELECT 1 FROM public.sesiones_asistencia WHERE sesion_id=NEW.id AND estado='') OR EXISTS (
   SELECT 1 FROM public.sesiones_asistencia a JOIN public.inscripciones_inscripcion i ON i.id=a.inscripcion_id
   WHERE a.sesion_id=NEW.id AND (i.grupo_id<>NEW.grupo_id OR i.deportista_id<>a.deportista_id OR i.fecha_ingreso>NEW.fecha OR (i.fecha_salida IS NOT NULL AND i.fecha_salida<=NEW.fecha))
  ) OR EXISTS (
   SELECT 1 FROM public.inscripciones_inscripcion i WHERE i.grupo_id=NEW.grupo_id AND i.fecha_ingreso<=NEW.fecha AND (i.fecha_salida IS NULL OR i.fecha_salida>NEW.fecha)
   AND NOT EXISTS (SELECT 1 FROM public.sesiones_asistencia a WHERE a.sesion_id=NEW.id AND a.inscripcion_id=i.id)
  ) THEN RAISE EXCEPTION 'Cierre exige padrón elegible completo con estados explícitos' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER zdb_sesion_cierre_guardia BEFORE INSERT OR UPDATE ON public.sesiones_sesion FOR EACH ROW EXECUTE FUNCTION public.zdb_sesion_cierre_guardia();

CREATE FUNCTION public.zdb_ejecucion_guardia() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE total bigint; duracion numeric; p public.sesiones_plansesion; s public.sesiones_sesion;
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Se conserva evidencia de ejecución' USING ERRCODE='23514'; END IF;
 IF TG_OP='UPDATE' AND (OLD.finalizada_en IS NOT NULL OR ROW(NEW.sesion_id,NEW.creada_por_id,NEW.creada_en) IS DISTINCT FROM ROW(OLD.sesion_id,OLD.creada_por_id,OLD.creada_en)) THEN
  RAISE EXCEPTION 'Ejecución finalizada o identidad inmutable' USING ERRCODE='23514'; END IF;
 IF TG_OP='INSERT' AND NEW.finalizada_en IS NOT NULL THEN RAISE EXCEPTION 'Registra actividades antes de finalizar' USING ERRCODE='23514'; END IF;
 SELECT * INTO p FROM public.sesiones_plansesion WHERE id=NEW.plan_id;
 SELECT * INTO s FROM public.sesiones_sesion WHERE id=NEW.sesion_id;
 IF p.sesion_id<>NEW.sesion_id OR NOT p.sellado THEN RAISE EXCEPTION 'Plan ajeno o no sellado' USING ERRCODE='23514'; END IF;
 IF NEW.finalizada_en IS NOT NULL THEN
  IF NOT s.asistencia_confirmada OR NEW.finalizada_por_id<>s.profesor_id OR NOT public.zdb_tiene_rol(NEW.finalizada_por_id,'profesor') THEN RAISE EXCEPTION 'Cierre exige docente responsable y asistencia definitiva' USING ERRCODE='23514'; END IF;
  IF (NEW.inicio AT TIME ZONE 'America/Bogota')::date<>s.fecha OR NEW.fin>statement_timestamp() OR NEW.fin-NEW.inicio>interval '24 hours' THEN
   RAISE EXCEPTION 'Intervalo real incompatible' USING ERRCODE='23514'; END IF;
  SELECT sum(minutos) INTO total FROM public.sesiones_actividadejecutada WHERE ejecucion_id=NEW.id;
  duracion:=extract(epoch FROM (NEW.fin-NEW.inicio))/60;
  IF total IS NULL OR total>duracion OR EXISTS (
   SELECT 1 FROM public.sesiones_tareasesion t WHERE t.plan_id=NEW.plan_id AND NOT EXISTS (SELECT 1 FROM public.sesiones_actividadejecutada a WHERE a.ejecucion_id=NEW.id AND a.tarea_id=t.id)
  ) OR EXISTS (
   SELECT 1 FROM public.sesiones_actividadejecutada a JOIN public.sesiones_tareasesion t ON t.id=a.tarea_id WHERE a.ejecucion_id=NEW.id AND t.plan_id<>NEW.plan_id
  ) THEN RAISE EXCEPTION 'Actividades incompletas, ajenas o duración incoherente' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER zdb_ejecucion_guardia BEFORE INSERT OR UPDATE OR DELETE ON public.sesiones_ejecucionsesion FOR EACH ROW EXECUTE FUNCTION public.zdb_ejecucion_guardia();

CREATE FUNCTION public.zdb_actividad_real_guardia() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE dato public.sesiones_ejecucionsesion; padre bigint;
BEGIN
 FOR padre IN SELECT CASE WHEN TG_OP='INSERT' THEN NULL ELSE OLD.ejecucion_id END UNION SELECT CASE WHEN TG_OP='DELETE' THEN NULL ELSE NEW.ejecucion_id END LOOP
  IF padre IS NULL THEN CONTINUE; END IF;
  SELECT * INTO dato FROM public.sesiones_ejecucionsesion WHERE id=padre FOR UPDATE;
  IF dato.finalizada_en IS NOT NULL THEN RAISE EXCEPTION 'Actividad finalizada inmutable' USING ERRCODE='23514'; END IF;
 END LOOP;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 SELECT * INTO dato FROM public.sesiones_ejecucionsesion WHERE id=NEW.ejecucion_id;
 IF NOT EXISTS (SELECT 1 FROM public.sesiones_tareasesion WHERE id=NEW.tarea_id AND plan_id=dato.plan_id) THEN RAISE EXCEPTION 'Tarea ajena al plan ejecutado' USING ERRCODE='23514'; END IF;
 IF (NEW.resultado='omitida' AND (btrim(NEW.motivo_omision)='' OR NEW.adaptacion_metodologica<>'')) OR (NEW.resultado<>'omitida' AND (btrim(NEW.descripcion)='' OR NEW.motivo_omision<>'')) OR
 (NEW.resultado='modificada' AND btrim(NEW.adaptacion_metodologica)='') OR (NEW.resultado='realizada' AND NEW.adaptacion_metodologica<>'') THEN
  RAISE EXCEPTION 'Resultado real sin descripción, adaptación o motivo coherentes' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER zdb_actividad_real_guardia BEFORE INSERT OR UPDATE OR DELETE ON public.sesiones_actividadejecutada FOR EACH ROW EXECUTE FUNCTION public.zdb_actividad_real_guardia();

CREATE FUNCTION public.zdb_correccion_asistencia() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE a public.sesiones_asistencia; ev public.sesiones_eventosesion;
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Corrección inmutable' USING ERRCODE='23514'; END IF;
 SELECT * INTO a FROM public.sesiones_asistencia WHERE id=NEW.asistencia_id FOR UPDATE;
 SELECT * INTO ev FROM public.sesiones_eventosesion WHERE id=NEW.evento_id;
 IF NOT public.zdb_tiene_rol(NEW.actor_id,'administrador') OR NOT EXISTS (SELECT 1 FROM public.cuentas_usuario WHERE id=NEW.actor_id AND is_active) OR btrim(NEW.motivo)='' OR a.estado<>NEW.anterior OR NOT EXISTS (SELECT 1 FROM public.sesiones_sesion WHERE id=a.sesion_id AND asistencia_confirmada) THEN
  RAISE EXCEPTION 'Corrección exige administración vigente, cierre y valor anterior' USING ERRCODE='23514'; END IF;
 IF ev.sesion_id<>a.sesion_id OR ev.actor_id<>NEW.actor_id OR ev.operacion<>'corregir_asistencia' OR (ev.solicitud->'datos'->>'deportista')::bigint IS DISTINCT FROM a.deportista_id OR ev.solicitud->'datos'->>'anterior' IS DISTINCT FROM NEW.anterior OR ev.solicitud->'datos'->>'nuevo' IS DISTINCT FROM NEW.nuevo OR ev.solicitud->'datos'->>'motivo' IS DISTINCT FROM NEW.motivo THEN
  RAISE EXCEPTION 'Evento de corrección incompatible' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER zdb_correccion_guardia BEFORE INSERT OR UPDATE OR DELETE ON public.sesiones_correccionasistencia FOR EACH ROW EXECUTE FUNCTION public.zdb_correccion_asistencia();
CREATE FUNCTION public.zdb_aplicar_correccion_asistencia() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$ BEGIN
 UPDATE public.sesiones_asistencia SET estado=NEW.nuevo WHERE id=NEW.asistencia_id;
 RETURN NEW;
END $$;
CREATE TRIGGER zdb_aplicar_correccion AFTER INSERT ON public.sesiones_correccionasistencia FOR EACH ROW EXECUTE FUNCTION public.zdb_aplicar_correccion_asistencia();
CREATE TRIGGER zdb_evento_sesion_inmutable BEFORE UPDATE OR DELETE ON public.sesiones_eventosesion FOR EACH ROW EXECUTE FUNCTION public.zdb_e3_inmutable();
"""

REVERSE = """
DROP TRIGGER zdb_evento_sesion_inmutable ON public.sesiones_eventosesion;
DROP TRIGGER zdb_aplicar_correccion ON public.sesiones_correccionasistencia;
DROP TRIGGER zdb_correccion_guardia ON public.sesiones_correccionasistencia;
DROP FUNCTION public.zdb_aplicar_correccion_asistencia();
DROP FUNCTION public.zdb_correccion_asistencia();
DROP TRIGGER zdb_actividad_real_guardia ON public.sesiones_actividadejecutada;
DROP FUNCTION public.zdb_actividad_real_guardia();
DROP TRIGGER zdb_ejecucion_guardia ON public.sesiones_ejecucionsesion;
DROP FUNCTION public.zdb_ejecucion_guardia();
DROP TRIGGER zdb_sesion_cierre_guardia ON public.sesiones_sesion;
DROP FUNCTION public.zdb_sesion_cierre_guardia();
DROP TRIGGER zdb_asistencia_guardia ON public.sesiones_asistencia;
DROP FUNCTION public.zdb_asistencia_guardia();
"""


class Migration(migrations.Migration):
    dependencies = [('sesiones', '0004_actividadejecutada_correccionasistencia_and_more'), ('recursos', '0002_integridad_editorial')]
    operations = [
        migrations.RunSQL('UPDATE public.sesiones_asistencia a SET deportista_id=i.deportista_id FROM public.inscripciones_inscripcion i WHERE i.id=a.inscripcion_id', migrations.RunSQL.noop),
        migrations.AlterField(model_name='asistencia', name='deportista', field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='deportistas.deportista')),
        migrations.RunSQL(SQL, REVERSE),
    ]
