from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="EventoAcceso",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo", models.CharField(choices=[("ingreso", "Ingreso"), ("salida", "Salida"), ("fallo", "Intento fallido")], max_length=10)),
                ("fecha", models.DateTimeField(auto_now_add=True)),
                ("usuario", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "evento de acceso", "verbose_name_plural": "eventos de acceso", "ordering": ["-fecha"]},
        ),
    ]
