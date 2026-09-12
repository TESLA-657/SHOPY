"""
Commande de gestion : crée (ou met à jour) le superutilisateur admin
directement dans la base de données de production (PostgreSQL sur Render).

Les identifiants sont lus depuis les variables d'environnement :
    DJANGO_SUPERUSER_USERNAME
    DJANGO_SUPERUSER_EMAIL
    DJANGO_SUPERUSER_PASSWORD

Configurez ces variables dans le dashboard Render (Environment) puis
redéployez : `python manage.py ensure_superuser` sera exécuté par build.sh
après `migrate` et garantira que le compte admin existe toujours en
production (même si la base PostgreSQL a été recréée par Render).
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Crée ou met à jour le superutilisateur admin à partir des variables "
        "d'environnement DJANGO_SUPERUSER_USERNAME / EMAIL / PASSWORD. "
        "Idempotent : sans danger à relancer à chaque déploiement."
    )

    def handle(self, *args, **options):
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', '').strip()
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '').strip()
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '').strip()

        if not username or not email or not password:
            raise CommandError(
                "Variables d'environnement manquantes : DJANGO_SUPERUSER_USERNAME, "
                "DJANGO_SUPERUSER_EMAIL et DJANGO_SUPERUSER_PASSWORD doivent être "
                "définies (dashboard Render → Environment) avant le redéploiement."
            )

        User = get_user_model()

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            },
        )

        # Met à jour les champs afin que le compte reste fonctionnel
        # même après un reset/recréation de la base par Render.
        changed = False
        if user.email != email:
            user.email = email
            changed = True
        if not user.is_staff:
            user.is_staff = True
            changed = True
        if not user.is_superuser:
            user.is_superuser = True
            changed = True
        if not user.is_active:
            user.is_active = True
            changed = True

        # Le mot de passe n'est forcé que lors de la création (ou si vide),
        # pour ne pas reposer les identifiants choisis par l'admin ensuite.
        if created or not user.has_usable_password():
            user.set_password(password)
            changed = True

        if changed:
            user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(
                f"Superutilisateur admin '{username}' créé en base de données."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Superutilisateur admin '{username}' déjà présent, "
                "vérifié/mis à jour."
            ))