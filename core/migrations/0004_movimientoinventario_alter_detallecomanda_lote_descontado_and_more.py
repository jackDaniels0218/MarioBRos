from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0003_factura_detallefactura'),
    ]

    operations = [
        migrations.AlterField(
            model_name='detallecomanda',
            name='lote_descontado',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='detalles_descontados',
                to='core.loteinsumo',
            ),
        ),
        migrations.AlterField(
            model_name='factura',
            name='estado',
            field=models.CharField(
                choices=[
                    ('pendiente', 'Pendiente'),
                    ('pagada', 'Pagada'),
                    ('cancelada', 'Cancelada'),
                ],
                default='pendiente',
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name='MovimientoInventario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cantidad', models.DecimalField(decimal_places=2, max_digits=10)),
                ('fecha_hora', models.DateTimeField(auto_now_add=True)),
                ('revertido', models.BooleanField(default=False)),
                ('detalle', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='movimientos', to='core.detallecomanda')),
                ('lote', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='movimientos', to='core.loteinsumo')),
            ],
        ),
    ]