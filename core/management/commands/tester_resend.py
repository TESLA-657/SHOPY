"""
Commande de gestion : envoyer un email de test via Resend.

Usage :
    python manage.py tester_resend --to votre@email.com

Ne fait aucun appel a une fonctionnalite metier : uniquement verifies
que SHOPY sait envoyer un email.

La cle API est lue depuis la variable d'environnement RESEND_API_KEY.
Elle n'est jamais demandee ni affichee en clair.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.email_service import (
    envoyer_email_de_test,
    resend_est_configure,
)


class Command(BaseCommand):
    help = (
        "Envoie un email de test via Resend pour verifier la configuration. "
        "Necessite RESEND_API_KEY dans l'environnement."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--to',
            dest='destinataire',
            required=True,
            help='Adresse email qui recoit le message de test.',
        )

    def handle(self, *args, **options):
        destinataire = options['destinataire'].strip()

        if '@' not in destinataire:
            raise CommandError(
                "Adresse email invalide : {0}".format(destinataire)
            )

        if not getattr(settings, 'RESEND_ENABLED', True):
            self.stdout.write(self.style.WARNING(
                "RESEND_ENABLED=False : l'envoi est desactive."
            ))
            return

        if not resend_est_configure():
            raise CommandError(
                "RESEND_API_KEY n'est pas definie.\n"
                "  - En local : ajoutez-la dans le fichier .env (racine du projet), "
                "puis relancez la commande.\n"
                "  - En production : dashboard Render -> Service -> Environment.\n"
                "Verifiez aussi que le fichier .env est bien charge dans votre "
                "terminal avant de lancer la commande."
            )

        # On n'affiche jamais la cle, seulement sa presence.
        self.stdout.write("Configuration detectee.")
        self.stdout.write("  Expediteur : {0}".format(
            getattr(settings, 'RESEND_FROM_EMAIL', '(non defini)')
        ))
        self.stdout.write("  Destinataire : {0}".format(destinataire))
        self.stdout.write("  Envoi en cours...")

        try:
            reponse = envoyer_email_de_test(destinataire)
        except Exception as exc:
            raise CommandError(
                "Echec de l'envoi via Resend : {0}".format(exc)
            )

        identifiant = None
        if isinstance(reponse, dict):
            identifiant = reponse.get('id')
        else:
            identifiant = getattr(reponse, 'id', None)

        self.stdout.write(self.style.SUCCESS(
            "Email de test envoye avec succes via Resend."
        ))
        if identifiant:
            self.stdout.write("  Identifiant Resend : {0}".format(identifiant))
        self.stdout.write(
            "Verifiez la boite de reception (et le dossier spam) de {0}.".format(
                destinataire
            )
        )
