"""Guardias aditivas: propuestas sin facultad operativa y evidencia inmutable."""
from django.db import migrations


SQL = r"""
CREATE FUNCTION public.zdb_competencia_b1_guardia() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE enlace public.cuentas_enlaceidentidad; ultimo public.cuentas_eventocompetenciaemisora;
BEGIN
 IF TG_OP <> 'INSERT' THEN
  RAISE EXCEPTION 'Evidencia B1 inmutable' USING ERRCODE='23514';
 END IF;
 IF TG_TABLE_NAME = 'cuentas_competenciaemisora' THEN
  SELECT * INTO enlace FROM public.cuentas_enlaceidentidad WHERE id=NEW.enlace_identidad_id FOR UPDATE;
  IF enlace.id IS NULL OR NOT enlace.vigente OR enlace.usuario_id IS DISTINCT FROM NEW.usuario_id
   OR enlace.persona_id IS DISTINCT FROM NEW.persona_id OR enlace.version IS DISTINCT FROM NEW.version_enlace
   OR enlace.evidencia IS DISTINCT FROM NEW.evidencia_identidad THEN
   RAISE EXCEPTION 'Identidad acreditada incompatible con propuesta B1' USING ERRCODE='23514';
  END IF;
 ELSE
  PERFORM 1 FROM public.cuentas_competenciaemisora WHERE id=NEW.competencia_id FOR UPDATE;
  SELECT * INTO ultimo FROM public.cuentas_eventocompetenciaemisora
   WHERE competencia_id=NEW.competencia_id ORDER BY numero DESC LIMIT 1;
  IF ultimo.id IS NULL THEN
   IF NEW.numero<>1 OR NEW.anterior_id IS NOT NULL OR NEW.accion<>'propuesta'
    OR NEW.actor_id IS DISTINCT FROM (SELECT registrada_por_id FROM public.cuentas_competenciaemisora WHERE id=NEW.competencia_id) THEN
    RAISE EXCEPTION 'Origen B1 incompatible' USING ERRCODE='23514';
   END IF;
  ELSIF NEW.numero<>ultimo.numero+1 OR NEW.anterior_id IS DISTINCT FROM ultimo.id
   OR NEW.accion NOT IN ('revision','retiro') OR ultimo.accion='retiro' THEN
   RAISE EXCEPTION 'Version B1 obsoleta, rama o propuesta retirada' USING ERRCODE='23514';
  END IF;
 END IF;
 NEW.registrada_en := pg_catalog.statement_timestamp();
 RETURN NEW;
END $$;
CREATE TRIGGER zdb_competencia_b1_guardia BEFORE INSERT OR UPDATE OR DELETE
 ON public.cuentas_competenciaemisora FOR EACH ROW EXECUTE FUNCTION public.zdb_competencia_b1_guardia();
CREATE TRIGGER zdb_evento_competencia_b1_guardia BEFORE INSERT OR UPDATE OR DELETE
 ON public.cuentas_eventocompetenciaemisora FOR EACH ROW EXECUTE FUNCTION public.zdb_competencia_b1_guardia();

CREATE FUNCTION public.zdb_competencia_b1_completa() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM public.cuentas_eventocompetenciaemisora
  WHERE competencia_id=NEW.id AND numero=1 AND accion='propuesta' AND actor_id=NEW.registrada_por_id) THEN
  RAISE EXCEPTION 'Propuesta B1 exige primer evento en la misma transaccion' USING ERRCODE='23514';
 END IF;
 RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER zdb_competencia_b1_completa AFTER INSERT
 ON public.cuentas_competenciaemisora DEFERRABLE INITIALLY DEFERRED
 FOR EACH ROW EXECUTE FUNCTION public.zdb_competencia_b1_completa();
"""


class Migration(migrations.Migration):
    dependencies = [('cuentas', '0008_competencia_emisora_b1')]
    # Reversión deliberadamente no automática: no retirar guardias y perder evidencia.
    operations = [migrations.RunSQL(SQL)]
