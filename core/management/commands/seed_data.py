"""
Commande de gestion : insère les données de référence (catégories et plans
d'abonnement) dans la base de données.

Pourquoi ? Ces données existent en local dans db.sqlite3, mais la base
PostgreSQL de Render est créée vierge à chaque déploiement
(les migrations ne créent que le schéma). Cette commande, exécutée par
build.sh après `migrate`, garantit que le site en ligne dispose toujours
de ses catégories et de ses plans. Elle est idempotente.
"""
from django.core.management.base import BaseCommand

from core.models import Categorie, PlanAbonnement

# Données de référence : identiques aux catégories présentes en base locale
CATEGORIES = [
    {"nom": "Téléphones", "icone": "📱", "slug": "telephones"},
    {"nom": "Informatique", "icone": "💻", "slug": "informatique"},
    {"nom": "Maison", "icone": "🏠", "slug": "maison"},
    {"nom": "Mode", "icone": "👗", "slug": "mode"},
    {"nom": "Électronique", "icone": "⚡", "slug": "electronique"},
    {"nom": "Auto", "icone": "🚗", "slug": "auto"},
    {"nom": "Alimentation", "icone": "🍎", "slug": "alimentation"},
    {"nom": "Santé", "icone": "💊", "slug": "sante"},
    {"nom": "Terrain", "icone": "🏘️", "slug": "terrain"},
]

# Plans d'abonnement (limite_produits : -1 = illimité)
PLANS = [
    {"nom": "gratuit", "prix": 0, "limite_produits": 5, "duree_jours": 30},
    {"nom": "essentiel", "prix": 25000, "limite_produits": 10, "duree_jours": 30},
    {"nom": "pro", "prix": 60000, "limite_produits": 35, "duree_jours": 30},
    {"nom": "business", "prix": 120000, "limite_produits": -1, "duree_jours": 30},
]


class Command(BaseCommand):
    help = "Insère les catégories et plans d'abonnement manquants (idempotent)."

    def handle(self, *args, **options):
        nb_cat_created = 0
        nb_cat_exist = 0
        for data in CATEGORIES:
            _, created = Categorie.objects.get_or_create(
                slug=data["slug"], defaults=data
            )
            if created:
                nb_cat_created += 1
            else:
                nb_cat_exist += 1

        nb_plan_created = 0
        nb_plan_exist = 0
        for data in PLANS:
            _, created = PlanAbonnement.objects.get_or_create(
                nom=data["nom"], defaults=data
            )
            if created:
                nb_plan_created += 1
            else:
                nb_plan_exist += 1

        self.stdout.write(self.style.SUCCESS(
            f"Catégories : {nb_cat_created} créée(s), {nb_cat_exist} déjà présente(s)."
        ))
        self.stdout.write(self.style.SUCCESS(
            f"Plans d'abonnement : {nb_plan_created} créé(s), "
            f"{nb_plan_exist} déjà présent(s)."
        ))