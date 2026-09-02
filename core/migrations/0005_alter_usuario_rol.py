from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0004_movimientoinventario_alter_detallecomanda_lote_descontado_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='usuario',
            name='rol',
            field=models.CharField(
                choices=[
                    ('admin', 'Administrador'),
                    ('empleado', 'Empleado/Mesero'),
                    ('cajero', 'Cajero'),
                ],
                default='empleado',
                max_length=20,
            ),
        ),
    ]