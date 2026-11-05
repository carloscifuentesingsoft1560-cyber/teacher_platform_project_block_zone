"""Guardias aditivas de expedientes pendientes, sin competencias operativas."""
from django.db import migrations


SQL = r"""
CREATE FUNCTION public.zdb_b21_identidad(eid bigint, uid bigint, pid bigint, version integer, evidencia uuid)
RETURNS void LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE e public.cuentas_enlaceidentidad;
BEGIN
 SELECT * INTO e FROM public.cuentas_enlaceidentidad WHERE id=eid FOR UPDATE;
 IF e.id IS NULL OR NOT e.vigente OR e.usuario_id IS DISTINCT FROM uid
  OR e.persona_id IS DISTINCT FROM pid OR e.version IS DISTINCT FROM version
  OR e.evidencia IS DISTINCT FROM evidencia
  OR NOT EXISTS (SELECT 1 FROM public.cuentas_usuario WHERE id=uid AND is_active) THEN
  RAISE EXCEPTION 'Identidad B2.1 no acreditada o incompatible' USING ERRCODE='23514';
 END IF;
END $$;

CREATE FUNCTION public.zdb_b21_fundamentos(cid bigint, ceid bigint, mid bigint, meid bigint,
 registrador bigint, desde timestamptz DEFAULT NULL, hasta timestamptz DEFAULT NULL)
RETURNS void LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE c public.cuentas_competenciaemisora; m public.cuentas_mandatoinstitucional;
 ce public.cuentas_eventocompetenciaemisora; me public.cuentas_eventomandatoinstitucional;
BEGIN
 SELECT * INTO m FROM public.cuentas_mandatoinstitucional WHERE id=mid FOR UPDATE;
 SELECT * INTO c FROM public.cuentas_competenciaemisora WHERE id=cid FOR UPDATE;
 SELECT * INTO ce FROM public.cuentas_eventocompetenciaemisora WHERE competencia_id=cid ORDER BY numero DESC LIMIT 1;
 SELECT * INTO me FROM public.cuentas_eventomandatoinstitucional WHERE mandato_id=mid ORDER BY numero DESC LIMIT 1;
 IF c.id IS NULL OR m.id IS NULL OR ce.id IS NULL OR me.id IS NULL
  OR ce.id IS DISTINCT FROM ceid OR me.id IS DISTINCT FROM meid
  OR ce.accion='retiro' OR me.accion='retiro' OR c.disciplina_id<>m.disciplina_id
  OR c.persona_id=registrador OR m.persona_id=registrador OR c.persona_id=m.persona_id THEN
  RAISE EXCEPTION 'Fundamento B2.1 retirado, obsoleto, incompatible o autoacreditacion' USING ERRCODE='23514';
 END IF;
 PERFORM public.zdb_b21_identidad(c.enlace_identidad_id,c.usuario_id,c.persona_id,c.version_enlace,c.evidencia_identidad);
 PERFORM public.zdb_b21_identidad(m.enlace_identidad_id,m.usuario_id,m.persona_id,m.version_enlace,m.evidencia_identidad);
 IF desde IS NOT NULL AND (desde<ce.vigente_desde_propuesta OR desde<me.vigente_desde_propuesta
  OR (ce.vigente_hasta_propuesta IS NOT NULL AND (hasta IS NULL OR hasta>ce.vigente_hasta_propuesta))
  OR (me.vigente_hasta_propuesta IS NOT NULL AND (hasta IS NULL OR hasta>me.vigente_hasta_propuesta))) THEN
  RAISE EXCEPTION 'Intervalo B2.1 fuera de fundamentos propuestos' USING ERRCODE='23514';
 END IF;
END $$;

CREATE FUNCTION public.zdb_b21_guardia() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE padre jsonb; ultimo jsonb; tabla_padre text; tabla_evento text; campo text;
 tipo text; padre_id bigint; otra_clave boolean;
BEGIN
 IF TG_OP<>'INSERT' THEN
  RAISE EXCEPTION 'Historia B2.1 inmutable' USING ERRCODE='23514';
 END IF;
 -- Serialización compartida con roles e identidad. Sin permisos derivados del expediente.
 PERFORM id FROM public.cuentas_usuario ORDER BY id FOR UPDATE;
 IF TG_TABLE_NAME IN ('cuentas_mandatoinstitucional','cuentas_acreditacionemisora') THEN
  IF NOT public.zdb_tiene_rol(NEW.registrada_por_id,'administrador') THEN
   RAISE EXCEPTION 'Registro B2.1 exige administracion vigente' USING ERRCODE='23514';
  END IF;
  PERFORM public.zdb_b21_identidad(NEW.enlace_registrador_id,NEW.registrada_por_id,
   NEW.persona_registradora_id,NEW.version_enlace_registrador,NEW.evidencia_registrador);
  IF TG_TABLE_NAME='cuentas_mandatoinstitucional' THEN
   PERFORM public.zdb_b21_identidad(NEW.enlace_identidad_id,NEW.usuario_id,NEW.persona_id,NEW.version_enlace,NEW.evidencia_identidad);
   IF NEW.persona_id=NEW.persona_registradora_id THEN
    RAISE EXCEPTION 'No se registra un mandato propio' USING ERRCODE='23514';
   END IF;
  ELSE
   PERFORM public.zdb_b21_fundamentos(NEW.competencia_id,NEW.evento_competencia_id,
    NEW.mandato_id,NEW.evento_mandato_id,NEW.persona_registradora_id);
  END IF;
 ELSE
  IF TG_TABLE_NAME='cuentas_eventomandatoinstitucional' THEN
   tabla_padre='cuentas_mandatoinstitucional'; tabla_evento='cuentas_eventomandatoinstitucional';
   campo='mandato_id'; padre_id=NEW.mandato_id; tipo='mandato';
  ELSE
   tabla_padre='cuentas_acreditacionemisora'; tabla_evento='cuentas_eventoacreditacionemisora';
   campo='acreditacion_id'; padre_id=NEW.acreditacion_id; tipo='acreditacion';
  END IF;
  IF NOT public.zdb_tiene_rol(NEW.actor_id,'administrador') THEN
   RAISE EXCEPTION 'Evento B2.1 exige administracion vigente' USING ERRCODE='23514';
  END IF;
  PERFORM public.zdb_b21_identidad(NEW.enlace_actor_id,NEW.actor_id,NEW.persona_actor_id,NEW.version_enlace_actor,NEW.evidencia_actor);
  EXECUTE format('SELECT to_jsonb(p) FROM public.%I p WHERE id=$1 FOR UPDATE',tabla_padre) INTO padre USING padre_id;
  IF padre IS NULL THEN RAISE EXCEPTION 'Expediente B2.1 inexistente' USING ERRCODE='23514'; END IF;
  IF tipo='mandato' THEN
   PERFORM public.zdb_b21_identidad((padre->>'enlace_identidad_id')::bigint,(padre->>'usuario_id')::bigint,
    (padre->>'persona_id')::bigint,(padre->>'version_enlace')::integer,(padre->>'evidencia_identidad')::uuid);
   IF (padre->>'persona_id')::bigint=NEW.persona_actor_id THEN
    RAISE EXCEPTION 'No se revisa un mandato propio' USING ERRCODE='23514';
   END IF;
  ELSE
   PERFORM public.zdb_b21_fundamentos((padre->>'competencia_id')::bigint,(padre->>'evento_competencia_id')::bigint,
    (padre->>'mandato_id')::bigint,(padre->>'evento_mandato_id')::bigint,NEW.persona_actor_id,
    NEW.vigente_desde_propuesta,NEW.vigente_hasta_propuesta);
  END IF;
  EXECUTE format('SELECT to_jsonb(e) FROM public.%I e WHERE %I=$1 ORDER BY numero DESC LIMIT 1',tabla_evento,campo)
   INTO ultimo USING padre_id;
  IF ultimo IS NULL THEN
   IF NEW.numero<>1 OR NEW.anterior_id IS NOT NULL OR NEW.accion<>'propuesta'
    OR NEW.actor_id IS DISTINCT FROM (padre->>'registrada_por_id')::bigint
    OR NEW.persona_actor_id IS DISTINCT FROM (padre->>'persona_registradora_id')::bigint
    OR NEW.enlace_actor_id IS DISTINCT FROM (padre->>'enlace_registrador_id')::bigint
    OR NEW.version_enlace_actor IS DISTINCT FROM (padre->>'version_enlace_registrador')::integer
    OR NEW.evidencia_actor IS DISTINCT FROM (padre->>'evidencia_registrador')::uuid THEN
    RAISE EXCEPTION 'Primer evento B2.1 incompatible' USING ERRCODE='23514';
   END IF;
  ELSIF NEW.numero<>(ultimo->>'numero')::integer+1 OR NEW.anterior_id IS DISTINCT FROM (ultimo->>'id')::bigint
   OR NEW.accion NOT IN ('revision','retiro') OR ultimo->>'accion'='retiro' THEN
   RAISE EXCEPTION 'Version B2.1 obsoleta o retirada' USING ERRCODE='23514';
  END IF;
  SELECT EXISTS (SELECT 1 FROM public.cuentas_eventomandatoinstitucional WHERE actor_id=NEW.actor_id AND clave=NEW.clave)
   OR EXISTS (SELECT 1 FROM public.cuentas_eventoacreditacionemisora WHERE actor_id=NEW.actor_id AND clave=NEW.clave) INTO otra_clave;
  IF otra_clave THEN RAISE EXCEPTION 'Clave B2.1 ya utilizada' USING ERRCODE='23505'; END IF;
  IF jsonb_typeof(NEW.solicitud) IS DISTINCT FROM 'object' OR NEW.solicitud->>'tipo' IS DISTINCT FROM tipo
   OR NEW.solicitud->>'operacion' IS DISTINCT FROM NEW.accion
   OR NEW.solicitud->'datos'->>'motivo' IS DISTINCT FROM NEW.motivo
   OR NEW.solicitud->'datos'->>'referencia_evidencia' IS DISTINCT FROM NEW.referencia_evidencia::text
   OR (NEW.solicitud->'datos'->>'vigente_desde_propuesta')::timestamptz IS DISTINCT FROM NEW.vigente_desde_propuesta
   OR (NEW.solicitud->'datos'->>'vigente_hasta_propuesta')::timestamptz IS DISTINCT FROM NEW.vigente_hasta_propuesta
   OR substring(NEW.clave::text,15,1)<>'4' OR substring(NEW.referencia_evidencia::text,15,1)<>'4' THEN
   RAISE EXCEPTION 'Solicitud o evidencia B2.1 incoherente' USING ERRCODE='23514';
  END IF;
  IF NEW.accion<>'propuesta' AND ((NEW.solicitud->>'expediente')::bigint IS DISTINCT FROM padre_id
   OR (NEW.solicitud->>'numero_esperado')::integer IS DISTINCT FROM NEW.numero-1) THEN
   RAISE EXCEPTION 'Solicitud de version B2.1 incompatible' USING ERRCODE='23514';
  END IF;
  IF NEW.accion='propuesta' THEN
   IF tipo='mandato' THEN
    IF (NEW.solicitud->>'enlace')::bigint IS DISTINCT FROM (padre->>'enlace_identidad_id')::bigint
     OR (NEW.solicitud->>'disciplina')::bigint IS DISTINCT FROM (padre->>'disciplina_id')::bigint
     OR NEW.solicitud->>'alcance' IS DISTINCT FROM padre->>'alcance_propuesto' THEN
     RAISE EXCEPTION 'Solicitud de mandato B2.1 incompatible' USING ERRCODE='23514';
    END IF;
   ELSE
    IF (NEW.solicitud->'referencias'->>'competencia_id')::bigint IS DISTINCT FROM (padre->>'competencia_id')::bigint
     OR (NEW.solicitud->'referencias'->>'evento_competencia_id')::bigint IS DISTINCT FROM (padre->>'evento_competencia_id')::bigint
     OR (NEW.solicitud->'referencias'->>'mandato_id')::bigint IS DISTINCT FROM (padre->>'mandato_id')::bigint
     OR (NEW.solicitud->'referencias'->>'evento_mandato_id')::bigint IS DISTINCT FROM (padre->>'evento_mandato_id')::bigint THEN
     RAISE EXCEPTION 'Solicitud de acreditacion B2.1 incompatible' USING ERRCODE='23514';
    END IF;
   END IF;
  END IF;
 END IF;
 NEW.registrada_en=pg_catalog.statement_timestamp();
 RETURN NEW;
END $$;

CREATE FUNCTION public.zdb_b21_completo() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE existe boolean;
BEGIN
 IF TG_TABLE_NAME='cuentas_mandatoinstitucional' THEN
  SELECT EXISTS (SELECT 1 FROM public.cuentas_eventomandatoinstitucional WHERE mandato_id=NEW.id AND numero=1 AND actor_id=NEW.registrada_por_id) INTO existe;
 ELSIF TG_TABLE_NAME='cuentas_acreditacionemisora' THEN
  SELECT EXISTS (SELECT 1 FROM public.cuentas_eventoacreditacionemisora WHERE acreditacion_id=NEW.id AND numero=1 AND actor_id=NEW.registrada_por_id) INTO existe;
 ELSE
  SELECT EXISTS (SELECT 1 FROM public.auditoria_cambioadministrativo WHERE entidad='cuentas.'||substring(TG_TABLE_NAME,9)
   AND identificador=NEW.id AND actor_id=NEW.actor_id AND accion=NEW.accion) INTO existe;
 END IF;
 IF NOT existe THEN RAISE EXCEPTION 'Expediente o auditoria B2.1 incompleto' USING ERRCODE='23514'; END IF;
 RETURN NULL;
END $$;

DO $$ DECLARE tabla text; BEGIN
 FOREACH tabla IN ARRAY ARRAY['cuentas_mandatoinstitucional','cuentas_eventomandatoinstitucional',
                              'cuentas_acreditacionemisora','cuentas_eventoacreditacionemisora'] LOOP
  EXECUTE format('CREATE TRIGGER zdb_b21_guardia BEFORE INSERT OR UPDATE OR DELETE ON public.%I FOR EACH ROW EXECUTE FUNCTION public.zdb_b21_guardia()',tabla);
  EXECUTE format('CREATE CONSTRAINT TRIGGER zdb_b21_completo AFTER INSERT ON public.%I DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.zdb_b21_completo()',tabla);
 END LOOP;
END $$;
"""


class Migration(migrations.Migration):
    dependencies = [('cuentas', '0010_mandatos_acreditaciones_b2_1'), ('auditoria', '0001_initial')]
    # No retirar guardias automáticamente ni perder evidencia histórica.
    operations = [migrations.RunSQL(SQL)]
