from django.db import migrations


def cargar(apps, schema_editor):
    Usuario = apps.get_model('cuentas', 'Usuario')
    Rol = apps.get_model('cuentas', 'PertenenciaRol')
    Evento = apps.get_model('cuentas', 'EventoRol')
    from django.utils import timezone
    ahora = timezone.now()
    for u in Usuario.objects.all():
        vigente = u.is_active or u.rol != "coordinador"
        r = Rol.objects.create(usuario_id=u.pk, rol=u.rol, vigente=vigente,
            fecha_inicio=ahora, fecha_fin=None if vigente else ahora)
        Evento.objects.create(pertenencia_id=r.pk, actor_id=None, accion='migracion',
            motivo='Rol preexistente; no acredita identidad ni autor histórico.', version=1)


SQL = r"""
CREATE FUNCTION public.zdb_tiene_rol(uid bigint, papel text) RETURNS boolean
LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT EXISTS(SELECT 1 FROM public.cuentas_pertenenciarol r
 JOIN public.cuentas_usuario u ON u.id=r.usuario_id
 WHERE u.id=uid AND u.is_active AND r.rol=papel AND r.vigente
 AND r.fecha_inicio<=pg_catalog.statement_timestamp());
$$;
CREATE FUNCTION public.zdb_rol_principal_compatible() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE r public.cuentas_pertenenciarol%ROWTYPE;
BEGIN
 IF TG_OP='UPDATE' AND OLD.rol IS DISTINCT FROM NEW.rol THEN
   FOR r IN SELECT * FROM public.cuentas_pertenenciarol WHERE usuario_id=NEW.id AND rol=OLD.rol AND vigente FOR UPDATE LOOP
     UPDATE public.cuentas_pertenenciarol SET vigente=false, fecha_fin=pg_catalog.statement_timestamp(), version=version+1 WHERE id=r.id;
     INSERT INTO public.cuentas_eventorol(pertenencia_id,actor_id,accion,motivo,fecha,version)
       VALUES(r.id,NULL,'revocar','Cambio de rol principal compatible',pg_catalog.statement_timestamp(),r.version+1);
   END LOOP;
 END IF;
 IF NOT NEW.is_active THEN
   IF NEW.rol<>'coordinador' AND (TG_OP='INSERT' OR OLD.rol IS DISTINCT FROM NEW.rol)
     AND NOT EXISTS(SELECT 1 FROM public.cuentas_pertenenciarol WHERE usuario_id=NEW.id AND rol=NEW.rol AND vigente) THEN
     INSERT INTO public.cuentas_pertenenciarol(usuario_id,rol,vigente,fecha_inicio,fecha_fin,version)
       VALUES(NEW.id,NEW.rol,true,pg_catalog.statement_timestamp(),NULL,1) RETURNING * INTO r;
     INSERT INTO public.cuentas_eventorol(pertenencia_id,actor_id,accion,motivo,fecha,version)
       VALUES(r.id,NULL,'compatibilidad','Cuenta inactiva: rol sin acceso efectivo',pg_catalog.statement_timestamp(),1);
   END IF;
   FOR r IN SELECT * FROM public.cuentas_pertenenciarol WHERE usuario_id=NEW.id AND rol='coordinador' AND vigente FOR UPDATE LOOP
     UPDATE public.cuentas_pertenenciarol SET vigente=false, fecha_fin=pg_catalog.statement_timestamp(),version=version+1 WHERE id=r.id;
     INSERT INTO public.cuentas_eventorol(pertenencia_id,actor_id,accion,motivo,fecha,version)
       VALUES(r.id,NULL,'revocar','Cuenta desactivada',pg_catalog.statement_timestamp(),r.version+1);
   END LOOP;
 ELSIF TG_OP='INSERT' OR OLD.rol IS DISTINCT FROM NEW.rol THEN
   IF NOT EXISTS(SELECT 1 FROM public.cuentas_pertenenciarol WHERE usuario_id=NEW.id AND rol=NEW.rol AND vigente) THEN
     INSERT INTO public.cuentas_pertenenciarol(usuario_id,rol,vigente,fecha_inicio,fecha_fin,version)
       VALUES(NEW.id,NEW.rol,true,pg_catalog.statement_timestamp(),NULL,1) RETURNING * INTO r;
     INSERT INTO public.cuentas_eventorol(pertenencia_id,actor_id,accion,motivo,fecha,version)
       VALUES(r.id,NULL,'compatibilidad','Rol principal; responsable en auditoría administrativa',pg_catalog.statement_timestamp(),1);
   END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER zdb_rol_principal_compatible AFTER INSERT OR UPDATE OF rol,is_active
 ON public.cuentas_usuario FOR EACH ROW EXECUTE FUNCTION public.zdb_rol_principal_compatible();
CREATE FUNCTION public.zdb_evento_rol_inmutable() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN RAISE EXCEPTION 'Historial de roles inmutable' USING ERRCODE='23514'; END $$;
CREATE TRIGGER zdb_evento_rol_inmutable BEFORE UPDATE OR DELETE ON public.cuentas_eventorol
 FOR EACH ROW EXECUTE FUNCTION public.zdb_evento_rol_inmutable();
"""


def revertir(apps, schema_editor):
    Rol = apps.get_model('cuentas', 'PertenenciaRol')
    Usuario = apps.get_model('cuentas', 'Usuario')
    from django.db.models import Count
    if (apps.get_model('cuentas','Persona').objects.exists()
        or apps.get_model('cuentas','EventoRol').objects.exclude(accion='migracion').exists()
        or Rol.objects.filter(vigente=True).values('usuario_id').annotate(n=Count('id')).filter(n__gt=1).exists()
        or Usuario.objects.exclude(rol__in=['administrador','coordinador','profesor']).exists()):
        raise RuntimeError('No se revierte multirrol con datos incompatibles; conciliar sin perder historia.')


class Migration(migrations.Migration):
    dependencies = [('cuentas','0005_enlaceidentidad_eventorol_persona_pertenenciarol_and_more')]
    operations = [migrations.RunPython(cargar, migrations.RunPython.noop),
        migrations.RunSQL(SQL, reverse_sql='''DROP TRIGGER zdb_rol_principal_compatible ON public.cuentas_usuario;
DROP FUNCTION public.zdb_rol_principal_compatible();
DROP TRIGGER zdb_evento_rol_inmutable ON public.cuentas_eventorol;
DROP FUNCTION public.zdb_evento_rol_inmutable();
DROP FUNCTION public.zdb_tiene_rol(bigint,text);'''),
        migrations.RunPython(migrations.RunPython.noop, revertir)]
