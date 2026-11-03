from django.db import migrations


SQL = r"""
-- Completar referencias derivables de planes preexistentes, sin inventar contenido.
UPDATE public.sesiones_plansesion p SET programa_id=m.programa_id
FROM public.curriculo_mallaversion v JOIN public.curriculo_malla m ON m.id=v.identidad_id
WHERE p.malla_version_id=v.id;
UPDATE public.sesiones_plansesion p SET semana_id=c.semana_id, fase_curricular_id=s.fase_id
FROM public.curriculo_claseprevista c JOIN public.curriculo_semanacurricular s ON s.id=c.semana_id
WHERE p.clase_id=c.id;
UPDATE public.sesiones_plansesion p SET revision_anterior_id=a.id
FROM public.sesiones_plansesion a WHERE a.sesion_id=p.sesion_id AND a.numero=p.numero-1;
UPDATE public.sesiones_plansesion SET sellado=true;

CREATE FUNCTION public.zdb_plan_sesion_guardia() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog AS $$
DECLARE total bigint; duracion numeric; fases bigint;
BEGIN
 IF TG_OP='DELETE' THEN
  RAISE EXCEPTION 'Se conserva la historia de planes' USING ERRCODE='23514';
 END IF;
 IF TG_OP='UPDATE' AND OLD.sellado THEN
  RAISE EXCEPTION 'Plan sellado inmutable; crear revisión' USING ERRCODE='23514';
 END IF;
 IF TG_OP='INSERT' AND NEW.sellado THEN
  RAISE EXCEPTION 'El plan se sella después de sus tareas' USING ERRCODE='23514';
 END IF;
 IF TG_OP='UPDATE' AND NEW.sellado THEN
  SELECT sum(minutos),count(DISTINCT fase) INTO total,fases FROM public.sesiones_tareasesion WHERE plan_id=NEW.id;
  SELECT extract(epoch FROM (hora_fin-hora_inicio))/60 INTO duracion FROM public.sesiones_sesion WHERE id=NEW.sesion_id;
  IF total IS DISTINCT FROM duracion OR fases<>3 OR EXISTS (
   SELECT 1 FROM (SELECT CASE fase WHEN 'inicial' THEN 1 WHEN 'central' THEN 2 ELSE 3 END n,
    lag(CASE fase WHEN 'inicial' THEN 1 WHEN 'central' THEN 2 ELSE 3 END) OVER (ORDER BY orden) anterior
    FROM public.sesiones_tareasesion WHERE plan_id=NEW.id) t WHERE t.n<t.anterior
  ) THEN RAISE EXCEPTION 'Duración o secuencia de fases incoherente' USING ERRCODE='23514'; END IF;
  IF (NEW.numero=1 AND NEW.revision_anterior_id IS NOT NULL) OR (NEW.numero>1 AND NOT EXISTS (
   SELECT 1 FROM public.sesiones_plansesion WHERE id=NEW.revision_anterior_id AND sesion_id=NEW.sesion_id AND numero=NEW.numero-1 AND sellado
  )) THEN RAISE EXCEPTION 'Cadena de revisiones incoherente' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER zdb_plan_guardia BEFORE INSERT OR UPDATE OR DELETE ON public.sesiones_plansesion
FOR EACH ROW EXECUTE FUNCTION public.zdb_plan_sesion_guardia();

CREATE FUNCTION public.zdb_plan_hijo_guardia() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog AS $$
DECLARE padre bigint; cerrado boolean;
BEGIN
 FOR padre IN SELECT CASE WHEN TG_OP='INSERT' THEN NULL ELSE OLD.plan_id END
              UNION SELECT CASE WHEN TG_OP='DELETE' THEN NULL ELSE NEW.plan_id END LOOP
  IF padre IS NULL THEN CONTINUE; END IF;
  SELECT sellado INTO cerrado FROM public.sesiones_plansesion WHERE id=padre FOR UPDATE;
  IF cerrado THEN RAISE EXCEPTION 'Contenido de plan sellado inmutable' USING ERRCODE='23514'; END IF;
 END LOOP;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER zdb_tarea_guardia BEFORE INSERT OR UPDATE OR DELETE ON public.sesiones_tareasesion
FOR EACH ROW EXECUTE FUNCTION public.zdb_plan_hijo_guardia();
CREATE TRIGGER zdb_competencia_plan_guardia BEFORE INSERT OR UPDATE OR DELETE ON public.sesiones_competenciaplan
FOR EACH ROW EXECUTE FUNCTION public.zdb_plan_hijo_guardia();
"""

REVERSE = """
DROP TRIGGER zdb_competencia_plan_guardia ON public.sesiones_competenciaplan;
DROP TRIGGER zdb_tarea_guardia ON public.sesiones_tareasesion;
DROP FUNCTION public.zdb_plan_hijo_guardia();
DROP TRIGGER zdb_plan_guardia ON public.sesiones_plansesion;
DROP FUNCTION public.zdb_plan_sesion_guardia();
"""


class Migration(migrations.Migration):
    dependencies = [('sesiones', '0002_plansesion_fase_curricular_plansesion_programa_and_more')]
    operations = [migrations.RunSQL(SQL, REVERSE)]
