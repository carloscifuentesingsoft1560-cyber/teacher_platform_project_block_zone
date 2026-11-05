"""Escenario A. Irreversible: no retirar protecciones dejando historia existente.

0004 sin 0005 no es una instalación habilitada. No modifica guardias anteriores.
"""
from django.db import migrations

SQL = r"""
CREATE FUNCTION public.zdb_b23_base(vid bigint) RETURNS void
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE v public.deportistas_propuestadecisionfuncionalversion;
 x public.deportistas_expedienteautorizacionfuncional;
 a public.cuentas_acreditacionemisora; e public.cuentas_eventoacreditacionemisora;
 enlace public.cuentas_enlaceidentidad;
BEGIN
 SELECT * INTO v FROM public.deportistas_propuestadecisionfuncionalversion WHERE id=vid FOR UPDATE;
 SELECT * INTO x FROM public.deportistas_expedienteautorizacionfuncional WHERE id=v.expediente_id FOR UPDATE;
 SELECT * INTO enlace FROM public.cuentas_enlaceidentidad WHERE id=x.enlace_identidad_id FOR UPDATE;
 IF enlace.id IS NULL OR NOT enlace.vigente OR enlace.deportista_id IS DISTINCT FROM x.deportista_id
  OR enlace.persona_id IS DISTINCT FROM x.persona_id OR enlace.version IS DISTINCT FROM x.version_enlace
  OR enlace.evidencia IS DISTINCT FROM x.evidencia_identidad THEN
  RAISE EXCEPTION 'Identidad destinataria incompatible o revocada' USING ERRCODE='23514'; END IF;
 SELECT * INTO a FROM public.cuentas_acreditacionemisora WHERE id=v.acreditacion_id FOR UPDATE;
 SELECT * INTO e FROM public.cuentas_eventoacreditacionemisora WHERE acreditacion_id=a.id ORDER BY numero DESC LIMIT 1;
 IF a.id IS NULL OR e.id IS DISTINCT FROM v.evento_acreditacion_id OR e.accion='retiro'
  OR v.desde_propuesta<e.vigente_desde_propuesta OR (e.vigente_hasta_propuesta IS NOT NULL AND v.hasta_propuesta>e.vigente_hasta_propuesta)
  OR x.persona_id=a.persona_registradora_id THEN
  RAISE EXCEPTION 'Antecedente pendiente incompatible, obsoleto o autorregistro' USING ERRCODE='23514'; END IF;
 PERFORM public.zdb_b21_identidad(a.enlace_registrador_id,a.registrada_por_id,a.persona_registradora_id,a.version_enlace_registrador,a.evidencia_registrador);
 PERFORM public.zdb_b21_fundamentos(a.competencia_id,a.evento_competencia_id,a.mandato_id,a.evento_mandato_id,
  a.persona_registradora_id,v.desde_propuesta,v.hasta_propuesta);
 IF NOT EXISTS(SELECT 1 FROM public.cuentas_competenciaemisora c JOIN public.cuentas_mandatoinstitucional m ON m.id=a.mandato_id
  WHERE c.id=a.competencia_id AND c.disciplina_id=x.disciplina_id AND m.disciplina_id=x.disciplina_id
   AND c.persona_id<>x.persona_id AND m.persona_id<>x.persona_id) THEN
  RAISE EXCEPTION 'Separación de identidades o disciplina incompatible' USING ERRCODE='23514'; END IF;
END $$;

CREATE FUNCTION public.zdb_b23_alcance(aid bigint) RETURNS void
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE a public.deportistas_alcancedecisionfuncional; ep public.biblioteca_eventoperfilfuncional;
 ec public.biblioteca_eventocorrespondenciafuncional; cv public.biblioteca_correspondenciafuncionalversion; d bigint;
BEGIN
 SELECT * INTO a FROM public.deportistas_alcancedecisionfuncional WHERE id=aid;
 SELECT * INTO ep FROM public.biblioteca_eventoperfilfuncional WHERE version_id=a.perfil_version_id ORDER BY numero DESC LIMIT 1;
 SELECT x.disciplina_id INTO d FROM public.deportistas_propuestadecisionfuncionalversion v
  JOIN public.deportistas_expedienteautorizacionfuncional x ON x.id=v.expediente_id WHERE v.id=a.version_id;
 IF ep.id IS NULL OR ep.id IS DISTINCT FROM a.evento_perfil_id OR ep.accion='retiro'
  OR NOT EXISTS(SELECT 1 FROM public.biblioteca_perfilfuncionalversion p JOIN public.biblioteca_perfilfuncional i ON i.id=p.perfil_id
   WHERE p.id=a.perfil_version_id AND i.disciplina_id=d AND NOT EXISTS(SELECT 1 FROM public.biblioteca_perfilfuncionalversion n WHERE n.perfil_id=p.perfil_id AND n.numero>p.numero)) THEN
  RAISE EXCEPTION 'Perfil propuesto incompatible, retirado o sustituido' USING ERRCODE='23514'; END IF;
 IF a.correspondencia_version_id IS NOT NULL THEN
  SELECT * INTO cv FROM public.biblioteca_correspondenciafuncionalversion WHERE id=a.correspondencia_version_id;
  SELECT * INTO ec FROM public.biblioteca_eventocorrespondenciafuncional WHERE version_id=cv.id ORDER BY numero DESC LIMIT 1;
  IF cv.id IS NULL OR cv.perfil_version_id IS DISTINCT FROM a.perfil_version_id OR cv.evento_perfil_id IS DISTINCT FROM ep.id
   OR ec.id IS DISTINCT FROM a.evento_correspondencia_id OR ec.accion='retiro'
   OR EXISTS(SELECT 1 FROM public.biblioteca_correspondenciafuncionalversion WHERE correspondencia_id=cv.correspondencia_id AND numero>cv.numero)
   OR d IS DISTINCT FROM public.zdb_b22_destino(cv.correspondencia_id) THEN
   RAISE EXCEPTION 'Correspondencia propuesta incompatible u obsoleta' USING ERRCODE='23514'; END IF;
 END IF;
END $$;

CREATE FUNCTION public.zdb_b23_guardia() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE j jsonb; vid bigint; ultimo bigint; anterior public.deportistas_eventoexpedientefuncional;
 v public.deportistas_propuestadecisionfuncionalversion; v_acreditacion public.cuentas_acreditacionemisora;
 condicion public.deportistas_condiciondecisionfuncional; adaptacion public.biblioteca_adaptacionperfilfuncional;
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'Historia documental individual inmutable' USING ERRCODE='23514'; END IF;
 PERFORM id FROM public.cuentas_usuario ORDER BY id FOR UPDATE;
 j:=to_jsonb(NEW);
 IF j ? 'creada_en' THEN NEW.creada_en:=clock_timestamp(); END IF;
 IF j ? 'registrada_en' THEN NEW.registrada_en:=clock_timestamp(); END IF;
 IF TG_TABLE_NAME='deportistas_propuestadecisionfuncionalversion' THEN
  PERFORM id FROM public.deportistas_expedienteautorizacionfuncional WHERE id=NEW.expediente_id FOR UPDATE;
  SELECT * INTO v FROM public.deportistas_propuestadecisionfuncionalversion WHERE expediente_id=NEW.expediente_id ORDER BY numero DESC LIMIT 1;
  IF (v.id IS NULL AND (NEW.numero<>1 OR NEW.anterior_id IS NOT NULL)) OR
   (v.id IS NOT NULL AND (NEW.numero<>v.numero+1 OR NEW.anterior_id IS DISTINCT FROM v.id)) OR
   EXISTS(SELECT 1 FROM public.deportistas_eventoexpedientefuncional WHERE expediente_id=NEW.expediente_id AND accion='retiro') THEN
   RAISE EXCEPTION 'Versión no consecutiva o expediente retirado' USING ERRCODE='23514'; END IF;
  IF NEW.emitida_en_declarada>clock_timestamp() THEN RAISE EXCEPTION 'Emisión declarada futura' USING ERRCODE='23514'; END IF;
 ELSIF TG_TABLE_NAME='deportistas_eventoexpedientefuncional' THEN
  PERFORM id FROM public.deportistas_expedienteautorizacionfuncional WHERE id=NEW.expediente_id FOR UPDATE;
  SELECT * INTO anterior FROM public.deportistas_eventoexpedientefuncional WHERE expediente_id=NEW.expediente_id ORDER BY numero DESC LIMIT 1;
  SELECT * INTO v FROM public.deportistas_propuestadecisionfuncionalversion WHERE expediente_id=NEW.expediente_id ORDER BY numero DESC LIMIT 1;
  IF v.id IS NULL OR NEW.version_id IS DISTINCT FROM v.id OR
   (anterior.id IS NULL AND (NEW.numero<>1 OR NEW.anterior_id IS NOT NULL OR NEW.accion<>'propuesta' OR v.numero<>1)) OR
   (anterior.id IS NOT NULL AND (anterior.accion='retiro' OR NEW.numero<>anterior.numero+1 OR NEW.anterior_id IS DISTINCT FROM anterior.id
    OR (NEW.accion='propuesta' AND v.anterior_id IS DISTINCT FROM anterior.version_id)
    OR (NEW.accion<>'propuesta' AND v.id IS DISTINCT FROM anterior.version_id))) THEN
   RAISE EXCEPTION 'Cadena de eventos inválida o retiro terminal' USING ERRCODE='23514'; END IF;
  SELECT * INTO v_acreditacion FROM public.cuentas_acreditacionemisora WHERE id=v.acreditacion_id;
  IF v_acreditacion.registrada_por_id IS DISTINCT FROM NEW.actor_id OR v_acreditacion.persona_registradora_id IS DISTINCT FROM NEW.persona_actor_id
   OR NOT public.zdb_tiene_rol(NEW.actor_id,'administrador') THEN
   RAISE EXCEPTION 'Sin relación específica de registro documental; el rol no basta' USING ERRCODE='23514'; END IF;
  PERFORM public.zdb_b21_identidad(NEW.enlace_actor_id,NEW.actor_id,NEW.persona_actor_id,NEW.version_enlace_actor,NEW.evidencia_actor);
  IF NEW.accion<>'retiro' THEN
   PERFORM public.zdb_b23_base(v.id);
   PERFORM public.zdb_b23_alcance(id) FROM public.deportistas_alcancedecisionfuncional WHERE version_id=v.id;
  END IF;
 ELSE
  IF j ? 'version_id' THEN vid:=(j->>'version_id')::bigint;
  ELSIF j ? 'alcance_id' THEN SELECT version_id INTO vid FROM public.deportistas_alcancedecisionfuncional WHERE id=(j->>'alcance_id')::bigint;
  END IF;
  IF vid IS NOT NULL THEN
   PERFORM id FROM public.deportistas_propuestadecisionfuncionalversion WHERE id=vid FOR UPDATE;
   IF EXISTS(SELECT 1 FROM public.deportistas_eventoexpedientefuncional WHERE version_id=vid) THEN
    RAISE EXCEPTION 'Contenido sellado por primer evento' USING ERRCODE='23514'; END IF;
  END IF;
  IF TG_TABLE_NAME='deportistas_condiciondecisionfuncional' THEN
   IF NOT EXISTS(SELECT 1 FROM public.deportistas_alcancedecisionfuncional alcance JOIN public.biblioteca_condicionperfilfuncional c
    ON c.version_id=alcance.perfil_version_id WHERE alcance.id=NEW.alcance_id AND c.id=NEW.condicion_id) THEN
    RAISE EXCEPTION 'Condición ajena al alcance' USING ERRCODE='23514'; END IF;
  ELSIF TG_TABLE_NAME='deportistas_adaptaciondecisionfuncional' THEN
   SELECT * INTO condicion FROM public.deportistas_condiciondecisionfuncional WHERE id=NEW.condicion_individual_id;
   SELECT * INTO adaptacion FROM public.biblioteca_adaptacionperfilfuncional WHERE id=NEW.adaptacion_id;
   IF condicion.id IS NULL OR adaptacion.id IS NULL OR condicion.alcance_id IS DISTINCT FROM NEW.alcance_id
    OR condicion.modalidad<>'condicionar' OR adaptacion.condicion_id IS DISTINCT FROM condicion.condicion_id THEN
    RAISE EXCEPTION 'Adaptación no expresamente cubierta por la condición individual' USING ERRCODE='23514'; END IF;
  ELSIF TG_TABLE_NAME='deportistas_referenciaevidenciafuncional' THEN
   IF substring(NEW.referencia::text,15,1)<>'4' OR substring(NEW.registro_custodia::text,15,1)<>'4' THEN
    RAISE EXCEPTION 'Solo referencias opacas UUID v4' USING ERRCODE='23514'; END IF;
  END IF;
 END IF;
 RETURN NEW;
END $$;

CREATE FUNCTION public.zdb_b23_completo() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 IF TG_TABLE_NAME='deportistas_expedienteautorizacionfuncional' THEN
  IF NOT EXISTS(SELECT 1 FROM public.deportistas_propuestadecisionfuncionalversion WHERE expediente_id=NEW.id AND numero=1) THEN
   RAISE EXCEPTION 'Primera versión obligatoria' USING ERRCODE='23514'; END IF;
 ELSIF TG_TABLE_NAME='deportistas_propuestadecisionfuncionalversion' THEN
  IF NOT EXISTS(SELECT 1 FROM public.deportistas_eventoexpedientefuncional WHERE version_id=NEW.id AND accion='propuesta')
   OR NOT EXISTS(SELECT 1 FROM public.deportistas_alcancedecisionfuncional WHERE version_id=NEW.id)
   OR NOT EXISTS(SELECT 1 FROM public.deportistas_referenciaevidenciafuncional WHERE version_id=NEW.id) THEN
   RAISE EXCEPTION 'Propuesta exige evento, alcance y referencia documental' USING ERRCODE='23514'; END IF;
 ELSE
  IF NOT EXISTS(SELECT 1 FROM public.auditoria_cambioadministrativo WHERE entidad='deportistas.eventoexpedientefuncional'
   AND identificador=NEW.id AND actor_id=NEW.actor_id AND accion=NEW.accion AND campos='["accion", "numero"]'::jsonb) THEN
   RAISE EXCEPTION 'Auditoría documental mínima obligatoria' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NULL;
END $$;
"""
TABLAS = ('expedienteautorizacionfuncional', 'propuestadecisionfuncionalversion', 'alcancedecisionfuncional',
          'condiciondecisionfuncional', 'adaptaciondecisionfuncional', 'referenciaevidenciafuncional', 'eventoexpedientefuncional')
for tabla in TABLAS:
    SQL += f'\nCREATE TRIGGER zdb_b23_guardia BEFORE INSERT OR UPDATE OR DELETE ON public.deportistas_{tabla} FOR EACH ROW EXECUTE FUNCTION public.zdb_b23_guardia();\n'
for tabla in ('expedienteautorizacionfuncional', 'propuestadecisionfuncionalversion', 'eventoexpedientefuncional'):
    SQL += f'\nCREATE CONSTRAINT TRIGGER zdb_b23_completo AFTER INSERT ON public.deportistas_{tabla} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.zdb_b23_completo();\n'


class Migration(migrations.Migration):
    dependencies = [('deportistas', '0004_expedientes_funcionales_b2_3'), ('biblioteca', '0005_guardias_catalogo_funcional_b2_2')]
    operations = [migrations.RunSQL(SQL)]
