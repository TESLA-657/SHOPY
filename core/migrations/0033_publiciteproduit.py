from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0032_vendeur_fidelite_active'),
    ]

    operations = [
        migrations.CreateModel(
            name='PubliciteProduit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('duree_jours', models.PositiveIntegerField(choices=[(7, '7 jours'), (15, '15 jours'), (30, '30 jours')])),
                ('montant', models.PositiveIntegerField()),
                ('numero_paiement', models.CharField(max_length=20)),
                ('reference', models.CharField(blank=True, max_length=100)),
                ('statut', models.CharField(choices=[('en_attente', 'Paiement en attente'), ('active', 'Active'), ('expiree', 'Expirée'), ('refusee', 'Refusée')], default='en_attente', max_length=20)),
                ('date_soumission', models.DateTimeField(auto_now_add=True)),
                ('date_debut', models.DateTimeField(blank=True, null=True)),
                ('date_fin', models.DateTimeField(blank=True, null=True)),
                ('produit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='publicites', to='core.produit')),
                ('vendeur', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='publicites', to='core.vendeur')),
            ],
        ),
    ]