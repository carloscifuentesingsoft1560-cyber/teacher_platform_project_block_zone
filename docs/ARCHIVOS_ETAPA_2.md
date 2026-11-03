# Archivos de Etapa 2

Inventario de la copia independiente respecto al manifiesto previo del proyecto original. No es un diff del remoto: ese remoto no contenía la aplicación local. Los paths son relativos a integracion/. Se conservan los originales.

## Archivos previos modificados

- `README.md`
- `backend/configuracion/settings.py`
- `backend/configuracion/urls.py`
- `backend/cuentas/admin.py`
- `backend/cuentas/coordinacion.py`
- `backend/cuentas/models.py`
- `backend/cuentas/permisos.py`
- `backend/cuentas/recuperacion.py`
- `backend/cuentas/serializers.py`
- `backend/cuentas/serializers_usuarios.py`
- `backend/cuentas/servicios_usuarios.py`
- `backend/cuentas/tests/test_coordinacion.py`
- `backend/cuentas/tests/test_usuarios.py`
- `backend/cuentas/views_usuarios.py`
- `backend/deportistas/documentos_views.py`
- `backend/deportistas/permisos.py`
- `backend/deportistas/servicios.py`
- `backend/deportistas/views.py`
- `backend/inscripciones/api_ejecucion.py`
- `backend/inscripciones/compatibilidad_propuestas.py`
- `backend/inscripciones/consultas_ascensos.py`
- `backend/inscripciones/servicios.py`
- `backend/inscripciones/servicios_ascensos.py`
- `backend/inscripciones/servicios_ejecucion.py`
- `backend/inscripciones/test_api_ascensos.py`
- `backend/inscripciones/test_api_ejecucion.py`
- `backend/inscripciones/test_correcciones_b3_b1.py`
- `backend/inscripciones/test_destinos_administrativos.py`
- `backend/inscripciones/test_ejecucion_b3_b1.py`
- `backend/inscripciones/test_integracion_b3_d.py`
- `backend/inscripciones/test_movimientos_b3_b2.py`
- `backend/inscripciones/test_plan_ascensos.py`
- `backend/inscripciones/test_seguridad_migracion_b1.py`
- `backend/inscripciones/views.py`
- `backend/inscripciones/views_ascensos.py`
- `backend/organizacion/alcance.py`
- `backend/organizacion/permisos.py`
- `backend/organizacion/servicios.py`
- `backend/organizacion/views.py`
- `backend/paneles/resumen.py`
- `docs/ARQUITECTURA.md`
- `docs/DECISIONES.md`
- `docs/MATRIZ_PERMISOS.md`
- `frontend/src/Aplicacion.jsx`
- `frontend/src/api/cliente.js`
- `frontend/src/autenticacion/ContextoAutenticacion.jsx`
- `frontend/src/componentes/EjecucionAscenso.jsx`
- `frontend/src/componentes/Estructura.jsx`
- `frontend/src/componentes/ListadoAscensos.jsx`
- `frontend/src/paginas/Coordinacion.jsx`
- `frontend/src/paginas/Usuarios.jsx`
- `frontend/src/pruebas/AscensosB3DRutas.test.jsx`
- `frontend/src/pruebas/EjecucionAscensos.test.jsx`
- `scripts/django_local.py`
- `scripts/pruebas_postgresql_aisladas.py`
- `scripts/test_infraestructura_aislada.py`

## Archivos nuevos

- `backend/cuentas/api_nucleo.py`
- `backend/cuentas/autorizacion.py`
- `backend/cuentas/migrations/0005_enlaceidentidad_eventorol_persona_pertenenciarol_and_more.py`
- `backend/cuentas/migrations/0006_roles_compatibilidad.py`
- `backend/cuentas/migrations/0007_remove_pertenenciarol_pertenencia_estado_coherente_and_more.py`
- `backend/cuentas/modelos_identidad.py`
- `backend/cuentas/modelos_roles.py`
- `backend/cuentas/servicios_identidad.py`
- `backend/cuentas/servicios_roles.py`
- `backend/cuentas/tests/test_concurrencia_roles.py`
- `backend/cuentas/tests/test_migracion_nucleo.py`
- `backend/cuentas/tests/test_nucleo.py`
- `backend/deportistas/test_identidad_multirrol.py`
- `backend/inscripciones/migrations/0005_facultades_multirrol.py`
- `backend/inscripciones/test_facultades_etapa2.py`
- `docs/ARCHIVOS_ETAPA_2.md`
- `docs/IMPLEMENTACION_ETAPA_2_NUCLEO.md`
- `frontend/src/componentes/RolesCuenta.jsx`
- `frontend/src/paginas/Identidades.jsx`
- `frontend/src/pruebas/GestionNucleo.test.jsx`
- `frontend/src/pruebas/NucleoInstitucional.test.jsx`

Las migraciones históricas, referencias privadas, dependencias y archivos de datos no se modificaron. El detalle de propósito, ensayos y limitaciones está en IMPLEMENTACION_ETAPA_2_NUCLEO.md.
