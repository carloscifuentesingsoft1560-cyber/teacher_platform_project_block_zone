from django.db import migrations

def cargar_catalogos(apps, schema_editor):
    Disciplina = apps.get_model("organizacion", "Disciplina")
    Nivel = apps.get_model("organizacion", "Nivel")
    disciplina, _ = Disciplina.objects.get_or_create(codigo="escalada", defaults={"nombre": "Escalada"})
    niveles = [
        ("ludico", "Lúdico"),
        ("nivel-1", "Nivel 1"),
        ("nivel-2", "Nivel 2"),
        ("especializacion", "Escuela de especialización semicompetitiva"),
        ("alto-rendimiento", "Alto rendimiento"),
    ]
    for orden, (codigo, nombre) in enumerate(niveles, 1):
        Nivel.objects.get_or_create(disciplina=disciplina, codigo=codigo, defaults={"nombre": nombre, "orden": orden})

class Migration(migrations.Migration):
    dependencies = [("organizacion", "0001_initial")]
    operations = [migrations.RunPython(cargar_catalogos, migrations.RunPython.noop)]
