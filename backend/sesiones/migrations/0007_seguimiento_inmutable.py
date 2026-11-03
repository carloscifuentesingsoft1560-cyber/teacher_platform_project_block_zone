from django.db import migrations

SQL = """
CREATE FUNCTION public.zdb_seguimiento_guardia() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE e public.sesiones_eventosesion; ultimo bigint;
BEGIN
 IF TG_OP <> 'INSERT' THEN
  RAISE EXCEPTION 'Seguimiento inmutable' USING ERRCODE='23514';
 END IF;
 PERFORM 1 FROM public.sesiones_sesion WHERE id=NEW.sesion_id FOR UPDATE;
 SELECT * INTO e FROM public.sesiones_eventosesion WHERE id=NEW.evento_id;
 SELECT id INTO ultimo FROM public.sesiones_seguimientopedagogico WHERE sesion_id=NEW.sesion_id ORDER BY id DESC LIMIT 1;
 IF e.id IS NULL OR e.sesion_id <> NEW.sesion_id OR e.actor_id <> NEW.actor_id OR e.operacion <> 'seguimiento'
 OR e.solicitud->>'comentario' IS DISTINCT FROM NEW.comentario
 OR e.solicitud->>'recomendaciones' IS DISTINCT FROM NEW.recomendaciones
 OR NEW.anterior_id IS DISTINCT FROM ultimo
 OR (e.detalle->>'anterior')::bigint IS DISTINCT FROM ultimo
 OR e.version <> (SELECT version FROM public.sesiones_sesion WHERE id=NEW.sesion_id)
 OR e.version <> (e.solicitud->>'version')::integer + 1
 OR (e.solicitud->>'sesion')::bigint IS DISTINCT FROM NEW.sesion_id
 OR length(NEW.comentario)>4000 OR length(NEW.recomendaciones)>4000
 OR btrim(NEW.comentario) = ''
 OR NOT EXISTS (SELECT 1 FROM public.cuentas_usuario u JOIN public.cuentas_pertenenciarol r ON r.usuario_id=u.id WHERE u.id=NEW.actor_id AND u.is_active AND r.rol='coordinador' AND r.vigente AND r.fecha_inicio<=clock_timestamp())
 THEN RAISE EXCEPTION 'Evidencia de seguimiento incoherente' USING ERRCODE='23514'; END IF;
 NEW.registrado_en := e.registrado_en;
 RETURN NEW;
END $$;
CREATE TRIGGER zdb_seguimiento_guardia BEFORE INSERT OR UPDATE OR DELETE ON public.sesiones_seguimientopedagogico FOR EACH ROW EXECUTE FUNCTION public.zdb_seguimiento_guardia();
"""


class Migration(migrations.Migration):
    dependencies = [('sesiones', '0006_seguimientopedagogico')]
    operations = [migrations.RunSQL(SQL, 'DROP TRIGGER zdb_seguimiento_guardia ON public.sesiones_seguimientopedagogico; DROP FUNCTION public.zdb_seguimiento_guardia();')]
