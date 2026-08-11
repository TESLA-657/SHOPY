from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .audit import AuditLog
from .models import (
    Abonnement,
    Client,
    Categorie,
    Commande,
    PaiementAbonnement,
    PaiementCommande,
    PaiementPanier,
    Panier,
    PanierItem,
    PlanAbonnement,
    Produit,
    Vendeur,
)


class AdminDashboardTests(TestCase):
    def test_admin_dashboard_page_loads_for_staff(self):
        user = User.objects.create_user(
            username="admin-test",
            email="admin@test.com",
            password="testpass123",
            is_staff=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("admin_dashboard"))

        self.assertEqual(response.status_code, 200)

    def test_admin_dashboard_links_to_filtered_vendor_lists(self):
        user = User.objects.create_user(
            username="admin-test-2",
            email="admin2@test.com",
            password="testpass123",
            is_staff=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("admin_dashboard"))

        self.assertContains(response, '?statut=all')
        self.assertContains(response, '?statut=actif')
        self.assertContains(response, '?statut=en_attente')
        self.assertContains(response, '?statut=suspendu')


class CatalogueTests(TestCase):
    def test_catalogue_page_loads_without_error(self):
        response = self.client.get(reverse("catalogue"))
        self.assertEqual(response.status_code, 200)


class AdminPaymentsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="admin-payments",
            email="admin-payments@test.com",
            password="testpass123",
            is_staff=True,
        )

    def test_admin_paiements_page_loads_for_staff(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("admin_paiements"))
        self.assertEqual(response.status_code, 200)

    def test_admin_paiements_commandes_page_loads_for_staff(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("admin_paiements_commandes"))
        self.assertEqual(response.status_code, 200)

    def test_admin_valide_paiement_abonnement(self):
        vendeur = Vendeur.objects.create(
            user=self.user,
            nom_boutique="Boutique Test",
            numero="+224600000011",
            ville="Conakry",
            statut="actif",
        )
        plan = PlanAbonnement.objects.create(
            nom="premium",
            prix=50000,
            limite_produits=20,
            duree_jours=30,
        )
        paiement = PaiementAbonnement.objects.create(
            vendeur=vendeur,
            plan=plan,
            numero_paiement="123456",
            montant=50000,
            statut="en_attente",
        )

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("admin_valider_paiement_abonnement", kwargs={"pk": paiement.pk}),
            {"action": "valider"},
        )

        self.assertEqual(response.status_code, 302)
        paiement.refresh_from_db()
        self.assertEqual(paiement.statut, "valide")

    def test_admin_validation_abonnement_active_le_statut_vendeur(self):
        vendeur = Vendeur.objects.create(
            user=self.user,
            nom_boutique="Boutique Test 2",
            numero="+224600000012",
            ville="Conakry",
            statut="suspendu",
        )
        plan = PlanAbonnement.objects.create(
            nom="pro",
            prix=60000,
            limite_produits=60,
            duree_jours=30,
        )
        PlanAbonnement.objects.get_or_create(
            nom="gratuit",
            defaults={"prix": 0, "limite_produits": 5, "duree_jours": 30},
        )
        abonnement = Abonnement.objects.create(
            vendeur=vendeur,
            plan=PlanAbonnement.objects.get(nom="gratuit"),
            statut="suspendu",
            date_fin=timezone.now() - timedelta(days=1),
        )
        paiement = PaiementAbonnement.objects.create(
            vendeur=vendeur,
            plan=plan,
            numero_paiement="654321",
            montant=60000,
            statut="en_attente",
        )

        self.client.force_login(self.user)
        self.client.post(
            reverse("admin_valider_paiement_abonnement", kwargs={"pk": paiement.pk}),
            {"action": "valider"},
        )

        abonnement.refresh_from_db()
        vendeur.refresh_from_db()
        self.assertEqual(abonnement.statut, "actif")
        self.assertEqual(abonnement.plan, plan)
        self.assertEqual(vendeur.statut, "actif")


class PanierCheckoutTests(TestCase):
    def test_commander_panier_cree_un_paiement_et_des_commandes_pour_plusieurs_vendeurs(self):
        user_client = User.objects.create_user(
            username="client-panier",
            email="client-panier@test.com",
            password="testpass123",
        )
        client = Client.objects.create(
            user=user_client,
            nom="Client Panier",
            numero="+224600000020",
            ville="Conakry",
        )

        vendeur_1 = Vendeur.objects.create(
            user=User.objects.create_user(username="vendeur-panier-1", email="vendeur1@test.com", password="testpass123"),
            nom_boutique="Boutique 1",
            numero="+224600000021",
            ville="Conakry",
            statut="actif",
        )
        vendeur_2 = Vendeur.objects.create(
            user=User.objects.create_user(username="vendeur-panier-2", email="vendeur2@test.com", password="testpass123"),
            nom_boutique="Boutique 2",
            numero="+224600000022",
            ville="Conakry",
            statut="actif",
        )
        categorie = Categorie.objects.create(nom="Test", slug="test", icone="📦")
        produit_1 = Produit.objects.create(
            vendeur=vendeur_1,
            nom="Produit A",
            photo="produits/a.jpg",
            prix=10000,
            quantite=10,
            description="Produit A",
            categorie=categorie,
            visible=True,
        )
        produit_2 = Produit.objects.create(
            vendeur=vendeur_2,
            nom="Produit B",
            photo="produits/b.jpg",
            prix=20000,
            quantite=5,
            description="Produit B",
            categorie=categorie,
            visible=True,
        )

        panier = Panier.objects.create(client=client)
        PanierItem.objects.create(panier=panier, produit=produit_1, quantite=2)
        PanierItem.objects.create(panier=panier, produit=produit_2, quantite=1)

        self.client.force_login(user_client)
        response = self.client.post(reverse("commander_panier"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(PaiementPanier.objects.count(), 1)
        self.assertEqual(Commande.objects.count(), 2)
        self.assertEqual(panier.items.count(), 0)

        paiement = PaiementPanier.objects.get(client=client)
        commandes = Commande.objects.filter(paiement_panier=paiement).order_by("pk")
        self.assertEqual(commandes[0].vendeur, vendeur_1)
        self.assertEqual(commandes[1].vendeur, vendeur_2)


class AdminDashboardMetricsTests(TestCase):
    def test_admin_dashboard_uses_real_metrics_for_last_7_days(self):
        staff_user = User.objects.create_user(
            username="admin-dashboard-metrics",
            email="admin-dashboard-metrics@test.com",
            password="testpass123",
            is_staff=True,
        )
        self.client.force_login(staff_user)

        now = timezone.now()
        login_client_log = AuditLog.objects.create(user=staff_user, action='login_client', ip_address='127.0.0.1')
        login_vendor_log = AuditLog.objects.create(user=staff_user, action='login_vendor', ip_address='127.0.0.1')
        signup_client_log = AuditLog.objects.create(user=staff_user, action='signup_client', ip_address='127.0.0.1')
        signup_vendor_log = AuditLog.objects.create(user=staff_user, action='signup_vendor', ip_address='127.0.0.1')
        product_view_log = AuditLog.objects.create(user=staff_user, action='product_view', ip_address='127.0.0.1')
        old_product_view_log = AuditLog.objects.create(user=staff_user, action='product_view', ip_address='127.0.0.1')

        AuditLog.objects.filter(pk=login_client_log.pk).update(timestamp=now - timedelta(days=2))
        AuditLog.objects.filter(pk=login_vendor_log.pk).update(timestamp=now - timedelta(days=4))
        AuditLog.objects.filter(pk=signup_client_log.pk).update(timestamp=now - timedelta(days=1))
        AuditLog.objects.filter(pk=signup_vendor_log.pk).update(timestamp=now - timedelta(days=5))
        AuditLog.objects.filter(pk=product_view_log.pk).update(timestamp=now - timedelta(days=6))
        AuditLog.objects.filter(pk=old_product_view_log.pk).update(timestamp=now - timedelta(days=20))

        vendeur = Vendeur.objects.create(
            user=User.objects.create_user(username='vendeur-dashboard', email='vendeur-dashboard@test.com', password='testpass123'),
            nom_boutique='Boutique Dashboard',
            numero='+224600000030',
            ville='Conakry',
            statut='actif',
        )
        categorie = Categorie.objects.create(nom='Test', slug='test-dashboard', icone='📦')
        produit = Produit.objects.create(
            vendeur=vendeur,
            nom='Produit Dashboard',
            photo='produits/dashboard.jpg',
            prix=10000,
            quantite=5,
            description='Produit dashboard',
            categorie=categorie,
            visible=True,
        )
        Commande.objects.create(
            produit=produit,
            vendeur=vendeur,
            nom_client='Client Dashboard',
            numero_client='+224600000031',
            ville_client='Conakry',
            quantite=1,
            prix_unitaire=10000,
            prix_total=10000,
            statut='acceptee',
            date_commande=now - timedelta(days=3),
        )
        Commande.objects.create(
            produit=produit,
            vendeur=vendeur,
            nom_client='Client Dashboard 2',
            numero_client='+224600000032',
            ville_client='Conakry',
            quantite=1,
            prix_unitaire=15000,
            prix_total=15000,
            statut='en_attente',
            date_commande=now - timedelta(days=30),
        )
        PaiementCommande.objects.create(
            commande=Commande.objects.first(),
            numero_paiement='pay-001',
            montant=10000,
            statut='valide',
        )
        PaiementPanier.objects.create(
            client=Client.objects.create(user=User.objects.create_user(username='client-dashboard-2', email='client-dashboard-2@test.com', password='testpass123'), nom='Client 2', numero='+224600000033', ville='Conakry'),
            montant_total=5000,
            numero_paiement='pay-002',
            statut='valide',
            date_validation=now - timedelta(days=2),
        )

        response = self.client.get(reverse('admin_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['logins_last_7'], 2)
        self.assertEqual(response.context['signups_last_7'], 2)
        self.assertEqual(response.context['product_views_last_7'], 1)
        self.assertEqual(response.context['orders_last_7'], 2)
        self.assertEqual(response.context['payments_last_7'], 2)
        self.assertEqual(response.context['revenus_7j'], 15000)


class SuppressionHistoriqueClientTests(TestCase):
    def setUp(self):
        self.password = "testpass123"

        # Utilisateur client
        self.user_client = User.objects.create_user(
            username="client@test.com",
            email="client@test.com",
            password=self.password
        )
        self.client_profile = Client.objects.create(
            user=self.user_client,
            nom="Client Test",
            numero="+224600000001",
            ville="Conakry"
        )

        # Vendeur + produit nécessaires pour les commandes
        self.user_vendeur = User.objects.create_user(
            username="vendeur_test",
            email="vendeur@test.com",
            password="vendeurpass123"
        )
        self.vendeur = Vendeur.objects.create(
            user=self.user_vendeur,
            nom_boutique="Boutique Test",
            numero="+224600000099",
            ville="Conakry",
            statut="actif"
        )
        self.categorie = Categorie.objects.create(
            nom="Test",
            slug="test",
            icone="📦"
        )
        self.produit = Produit.objects.create(
            vendeur=self.vendeur,
            nom="Produit Test",
            photo="produits/test.jpg",
            prix=10000,
            quantite=20,
            description="Produit pour tests",
            categorie=self.categorie,
            visible=True
        )

    def _creer_commande(self, jours_anciennete):
        commande = Commande.objects.create(
            produit=self.produit,
            vendeur=self.vendeur,
            nom_client=self.client_profile.nom,
            numero_client=self.client_profile.numero,
            ville_client=self.client_profile.ville,
            message="",
            quantite=1,
            prix_unitaire=10000,
            prix_total=10000
        )
        commande.date_commande = timezone.now() - timedelta(days=jours_anciennete)
        commande.save(update_fields=["date_commande"])
        return commande

    def test_mon_compte_affiche_banniere_si_commande_plus_30_jours(self):
        self.client.login(username=self.user_client.username, password=self.password)
        self._creer_commande(45)

        response = self.client.get(reverse("espace_client"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["proposer_suppression_historique"])

    def test_mon_compte_n_affiche_pas_banniere_si_aucune_commande_ancienne(self):
        self.client.login(username=self.user_client.username, password=self.password)
        self._creer_commande(10)

        response = self.client.get(reverse("espace_client"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["proposer_suppression_historique"])

    def test_post_suppression_supprime_seulement_commandes_plus_30_jours(self):
        self.client.login(username=self.user_client.username, password=self.password)

        ancienne = self._creer_commande(40)
        recente = self._creer_commande(5)

        url = reverse("supprimer_historique_commandes_client")
        response = self.client.post(url, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Commande.objects.filter(pk=ancienne.pk).exists())
        self.assertTrue(Commande.objects.filter(pk=recente.pk).exists())

    def test_post_suppression_sans_commande_ancienne_ne_supprime_rien(self):
        self.client.login(username=self.user_client.username, password=self.password)
        recente = self._creer_commande(3)

        url = reverse("supprimer_historique_commandes_client")
        response = self.client.post(url, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Commande.objects.filter(pk=recente.pk).exists())

    def test_post_suppression_redirige_si_non_connecte(self):
        url = reverse("supprimer_historique_commandes_client")
        response = self.client.post(url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/connexion-client/", response.url)
        self.assertIn("next=/mon-compte/supprimer-historique/", response.url)
