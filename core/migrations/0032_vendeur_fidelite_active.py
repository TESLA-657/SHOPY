from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0031_auditlog'),
    ]

    operations = [
        migrations.AddField(
            model_name='vendeur',
            name='fidelite_active',
            field=models.BooleanField(default=False),
        ),
    ]