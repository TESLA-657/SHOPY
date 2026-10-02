from datetime import timedelta
import json
import re

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from .audit import AuditLog
from .email_service import (
    email_bienvenue_client,
    email_bienvenue_vendeur,
    email_code_verification,
    envoyer,
    envoyer_email,
    envoyer_email_de_test,
    envoyer_email_smtp,
    expediteur,
    resend_est_configure,
    transport_actif,
)
from .models import (
    Abonnement,
    Client,
    Categorie,
    Commande,
    Favori,
    Notification,
    PaiementAbonnement,
    PaiementCommande,
    PaiementPanier,
    Panier,
    PanierItem,
    PasswordResetCode,
    PlanAbonnement,
    Produit,
    Vendeur,
)
from .views import CLE_CAPTCHA_SESSION


def captcha_pour(client, url):
    """
    Prepare une session avec une question CAPTCHA neuve et retourne la
    bonne reponse.

    Le champ « verification de securite » est obligatoire sur les deux
    formulaires d'inscription : tout test qui s'inscrit doit donc
    l'alimenter, sinon la vue refuse la creation du compte.
    La reponse attendue vit en session (jamais dans le HTML).
    """
    client.get(url)
    return client.session.get(CLE_CAPTCHA_SESSION)


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


class ResendEmailServiceTests(TestCase):
    """
    Service d'envoi d'emails Resend.

    Ces tests n'appellent JAMAIS l'API Resend : le SDK est simule.
    Ils verifient la configuration, la construction du payload et
    les garde-fous (pas de cle en dur, envoi desactive).
    """

    def test_cle_absente_renvoie_non_configure(self):
        with self.settings(RESEND_API_KEY="", RESEND_ENABLED=True):
            self.assertFalse(resend_est_configure())

    def test_desactive_renvoie_non_configure(self):
        with self.settings(RESEND_API_KEY="re_123", RESEND_ENABLED=False):
            self.assertFalse(resend_est_configure())

    def test_cle_presente_renvoie_configure(self):
        with self.settings(RESEND_API_KEY="re_123", RESEND_ENABLED=True):
            self.assertTrue(resend_est_configure())

    def test_expediteur_utilise_le_nom_et_l_adresse(self):
        with self.settings(RESEND_FROM_EMAIL="contact@shopy-guinee.com",
                           RESEND_FROM_NAME="SHOPY"):
            self.assertEqual(
                expediteur(), "SHOPY <contact@shopy-guinee.com>"
            )

    def test_expediteur_sans_nom_reste_l_adresse(self):
        with self.settings(RESEND_FROM_EMAIL="contact@shopy-guinee.com",
                           RESEND_FROM_NAME=""):
            self.assertEqual(expediteur(), "contact@shopy-guinee.com")

    def test_envoi_construit_le_payload_attendu_avec_sdk_simule(self):
        """Verifie le payload transmis au SDK, sans appel reseau."""
        from unittest import mock

        sent = {}

        def faux_send(params):
            sent.update(params)
            return {"id": "email_123"}

        with self.settings(RESEND_API_KEY="re_test_123",
                           RESEND_FROM_EMAIL="onboarding@resend.dev",
                           RESEND_FROM_NAME="SHOPY",
                           RESEND_ENABLED=True):
            with mock.patch("resend.Emails.send", side_effect=faux_send):
                reponse = envoyer_email(
                    destinataire="client@test.com",
                    sujet="Test SHOPY",
                    corps_texte="Bonjour",
                    corps_html="<p>Bonjour</p>",
                )

        self.assertEqual(reponse, {"id": "email_123"})
        # Le SDK attend "to" sous forme de liste.
        self.assertEqual(sent["to"], ["client@test.com"])
        self.assertEqual(sent["subject"], "Test SHOPY")
        self.assertEqual(sent["text"], "Bonjour")
        self.assertEqual(sent["html"], "<p>Bonjour</p>")
        self.assertEqual(sent["from"], "SHOPY <onboarding@resend.dev>")

    def test_envoi_refuse_si_desactive(self):
        from unittest import mock

        with self.settings(RESEND_API_KEY="re_test_123", RESEND_ENABLED=False):
            with mock.patch("resend.Emails.send") as m:
                with self.assertRaises(RuntimeError):
                    envoyer_email("client@test.com", "Test")
                m.assert_not_called()

    def test_envoi_refuse_si_cle_absente(self):
        from unittest import mock

        with self.settings(RESEND_API_KEY="", RESEND_ENABLED=True):
            with mock.patch("resend.Emails.send") as m:
                with self.assertRaises(RuntimeError):
                    envoyer_email("client@test.com", "Test")
                m.assert_not_called()

    def test_email_de_test_renvoie_sujet_attendu(self):
        from unittest import mock

        with self.settings(RESEND_API_KEY="re_test_123",
                           RESEND_FROM_EMAIL="onboarding@resend.dev",
                           RESEND_FROM_NAME="SHOPY",
                           RESEND_ENABLED=True):
            with mock.patch("resend.Emails.send",
                            return_value={"id": "email_test"}) as m:
                envoyer_email_de_test("client@test.com")

        params = m.call_args[0][0]
        self.assertIn("Resend", params["subject"])
        self.assertEqual(params["to"], ["client@test.com"])

    def test_copie_carbone_ne_reprend_pas_les_destinataires(self):
        """
        Regression : la copie carbone doit contenir les adresses
        copiees, jamais la liste des destinataires.
        """
        from unittest import mock

        with self.settings(RESEND_API_KEY="re_test_123",
                           RESEND_FROM_EMAIL="onboarding@resend.dev",
                           RESEND_FROM_NAME="SHOPY",
                           RESEND_ENABLED=True):
            with mock.patch("resend.Emails.send",
                            return_value={"id": "x"}) as m:
                envoyer_email(
                    destinataire=["client@test.com", "autre@test.com"],
                    sujet="Sujet",
                    corps_texte="Corps",
                    copie=["copie@test.com"],
                )

        params = m.call_args[0][0]
        self.assertEqual(params["cc"], ["copie@test.com"])
        # Les destinataires ne doivent pas fuiter en copie.
        self.assertNotIn("client@test.com", params["cc"])
        self.assertNotIn("autre@test.com", params["cc"])

    def test_copie_carbone_accepte_une_simple_adresse(self):
        from unittest import mock

        with self.settings(RESEND_API_KEY="re_test_123",
                           RESEND_FROM_EMAIL="onboarding@resend.dev",
                           RESEND_FROM_NAME="SHOPY",
                           RESEND_ENABLED=True):
            with mock.patch("resend.Emails.send",
                            return_value={"id": "x"}) as m:
                envoyer_email(
                    destinataire="client@test.com",
                    sujet="Sujet",
                    corps_texte="Corps",
                    copie="copie@test.com",
                )

        self.assertEqual(m.call_args[0][0]["cc"], ["copie@test.com"])


class EmailTransportSelectionTests(TestCase):
    """
    Point d'entree central `envoyer()` : choix Resend -> SMTP.

    Aucun appel reseau reel : le SDK Resend et le backend SMTP sont
    simules. On verifie le transport choisi, le repli, et surtout
    qu'une erreur d'envoi ne remonte jamais par defaut (comportement
    historique de SHOPY : un email non parti ne doit pas casser
    une commande, un paiement ou une inscription).
    """

    # ---------- Selection du transport ----------

    def test_resend_est_prioritaire_quand_la_cle_est_configuree(self):
        with self.settings(RESEND_API_KEY="re_123", RESEND_ENABLED=True):
            self.assertEqual(transport_actif(), "resend")

    def test_repli_smtp_quand_la_cle_est_absente(self):
        with self.settings(RESEND_API_KEY="", RESEND_ENABLED=True):
            # EMAIL_BACKEND est toujours defini par le projet.
            self.assertEqual(transport_actif(), "smtp")

    def test_repli_smtp_quand_resend_est_desactive(self):
        """RESEND_ENABLED=False doit basculer sur le SMTP."""
        with self.settings(RESEND_API_KEY="re_123", RESEND_ENABLED=False):
            self.assertEqual(transport_actif(), "smtp")

    def test_aucun_transport_si_tout_est_absent(self):
        with self.settings(RESEND_API_KEY="", RESEND_ENABLED=True,
                           EMAIL_BACKEND=""):
            self.assertEqual(transport_actif(), "aucun")

    def test_envoyer_utilise_resend_quand_configure(self):
        from unittest import mock

        with self.settings(RESEND_API_KEY="re_123", RESEND_ENABLED=True,
                           RESEND_FROM_EMAIL="onboarding@resend.dev",
                           RESEND_FROM_NAME="SHOPY"):
            with mock.patch("resend.Emails.send",
                            return_value={"id": "x"}) as send:
                with mock.patch("core.email_service.envoyer_email_smtp") as smtp:
                    resultat = envoyer("client@test.com", "Sujet", "Corps")

        self.assertTrue(resultat["envoye"])
        self.assertEqual(resultat["transport"], "resend")
        send.assert_called_once()
        # Le SMTP ne doit surtout pas etre sollicite.
        smtp.assert_not_called()

    def test_envoyer_utilise_smtp_quand_resend_absent(self):
        from unittest import mock

        with self.settings(RESEND_API_KEY="", RESEND_ENABLED=True):
            with mock.patch("resend.Emails.send") as send:
                with mock.patch(
                    "core.email_service.envoyer_email_smtp", return_value=1
                ) as smtp:
                    resultat = envoyer("client@test.com", "Sujet", "Corps")

        self.assertTrue(resultat["envoye"])
        self.assertEqual(resultat["transport"], "smtp")
        smtp.assert_called_once()
        send.assert_not_called()

    def test_repli_smtp_ne_tente_pas_resend(self):
        """Le repli ne doit jamais appeler le SDK Resend."""
        from unittest import mock

        with self.settings(RESEND_API_KEY="", RESEND_ENABLED=True):
            with mock.patch("resend.Emails.send") as send:
                with mock.patch(
                    "core.email_service.envoyer_email_smtp", return_value=1
                ):
                    envoyer("client@test.com", "Sujet", "Corps")

        send.assert_not_called()

    # ---------- Robustesse : ne rien casser ----------

    def test_erreur_resend_ne_leve_pas_par_defaut(self):
        """Comportement silencieux : une erreur ne doit rien casser."""
        from unittest import mock

        with self.settings(RESEND_API_KEY="re_123", RESEND_ENABLED=True):
            with mock.patch("resend.Emails.send",
                            side_effect=Exception("API key is invalid")):
                resultat = envoyer("client@test.com", "Sujet", "Corps")

        self.assertFalse(resultat["envoye"])
        self.assertEqual(resultat["transport"], "resend")
        self.assertIn("API key is invalid", resultat["erreur"])

    def test_erreur_resend_leve_si_fail_silently_false(self):
        from unittest import mock

        with self.settings(RESEND_API_KEY="re_123", RESEND_ENABLED=True):
            with mock.patch("resend.Emails.send",
                            side_effect=Exception("API key is invalid")):
                with self.assertRaises(Exception):
                    envoyer("client@test.com", "Sujet", "Corps",
                            fail_silently=False)

    def test_erreur_smtp_ne_leve_pas_par_defaut(self):
        from unittest import mock

        with self.settings(RESEND_API_KEY="", RESEND_ENABLED=True):
            with mock.patch("core.email_service.envoyer_email_smtp",
                            side_effect=Exception("SMTP indisponible")):
                resultat = envoyer("client@test.com", "Sujet", "Corps")

        self.assertFalse(resultat["envoye"])
        self.assertEqual(resultat["transport"], "smtp")
        self.assertIn("SMTP indisponible", resultat["erreur"])

    def test_aucun_transport_ne_leve_pas_par_defaut(self):
        """Meme sans aucun transport, l'appel doit rester sans effet."""
        with self.settings(RESEND_API_KEY="", RESEND_ENABLED=True,
                           EMAIL_BACKEND=""):
            resultat = envoyer("client@test.com", "Sujet", "Corps")

        self.assertFalse(resultat["envoye"])
        self.assertEqual(resultat["transport"], "aucun")

    def test_aucun_transport_leve_si_fail_silently_false(self):
        with self.settings(RESEND_API_KEY="", RESEND_ENABLED=True,
                           EMAIL_BACKEND=""):
            with self.assertRaises(RuntimeError):
                envoyer("client@test.com", "Sujet", "Corps",
                        fail_silently=False)

    def test_erreur_resend_ne_bascule_pas_sur_smtp(self):
        """
        Choix delibere : si Resend est configure mais echoue, on ne
        tente PAS le SMTP. Un double envoi est pire qu'un email perdu,
        et l'erreur doit rester visible dans les logs.
        """
        from unittest import mock

        with self.settings(RESEND_API_KEY="re_123", RESEND_ENABLED=True):
            with mock.patch("resend.Emails.send",
                            side_effect=Exception("echec")):
                with mock.patch("core.email_service.envoyer_email_smtp") as smtp:
                    envoyer("client@test.com", "Sujet", "Corps")

        smtp.assert_not_called()

    # ---------- Repli SMTP : compatibilite send_mail ----------

    def test_envoyer_email_smtp_transmet_les_bons_arguments(self):
        from unittest import mock

        with self.settings(DEFAULT_FROM_EMAIL="noreply@shopy-guinee.com"):
            with mock.patch("core.email_service.send_mail",
                            return_value=1) as sm:
                nb = envoyer_email_smtp(
                    destinataire="client@test.com",
                    sujet="Sujet",
                    corps_texte="Corps",
                    corps_html="<p>Corps</p>",
                )

        self.assertEqual(nb, 1)
        kwargs = sm.call_args.kwargs
        self.assertEqual(kwargs["recipient_list"], ["client@test.com"])
        self.assertEqual(kwargs["message"], "Corps")
        self.assertEqual(kwargs["html_message"], "<p>Corps</p>")
        self.assertEqual(kwargs["from_email"], "noreply@shopy-guinee.com")
        # Silence par defaut : ne doit pas casser l'appelant.
        self.assertTrue(kwargs["fail_silently"])

    def test_envoyer_email_smtp_accepte_plusieurs_destinataires(self):
        from unittest import mock

        with mock.patch("core.email_service.send_mail", return_value=2) as sm:
            nb = envoyer_email_smtp(
                destinataire=["a@test.com", "b@test.com"],
                sujet="Sujet",
                corps_texte="Corps",
            )

        self.assertEqual(nb, 2)
        self.assertEqual(
            sm.call_args.kwargs["recipient_list"], ["a@test.com", "b@test.com"]
        )

    def test_envoyer_email_smtp_ignore_destinataire_vide(self):
        from unittest import mock

        with mock.patch("core.email_service.send_mail") as sm:
            self.assertEqual(
                envoyer_email_smtp(destinataire="", sujet="S", corps_texte="C"),
                0,
            )
            self.assertEqual(
                envoyer_email_smtp(destinataire=None, sujet="S",
                                   corps_texte="C"),
                0,
            )
        sm.assert_not_called()

class AccountLifecycleEmailTests(TestCase):
    """
    E-mails de cycle de vie du compte : inscription client, inscription
    vendeur, mot de passe oublie et renvoi du code.

    Ces tests verifient que les vues appellent bien le service central
    et qu'un echec d'envoi ne bloque jamais la creation du compte.
    """

    def setUp(self):
        self.categorie = Categorie.objects.create(
            nom="Test cycle de vie", slug="test-cycle-vie", icone="x"
        )

    # ---------- Inscription client ----------

    def test_inscription_client_envoie_un_email_de_bienvenue(self):
        from unittest import mock

        with mock.patch("core.views.email_bienvenue_client") as env:
            env.return_value = {"envoye": True, "transport": "resend",
                                "erreur": None}
            response = self.client.post("/inscription-client/", {
                "nom": "Awa Diallo",
                "numero": "612000001",
                "ville": "Conakry",
                "email": "awa@test.com",
                "mot_de_passe": "motdepasse123",
                "confirmer_mot_de_passe": "motdepasse123",
                "captcha_answer": captcha_pour(
                    self.client, "/inscription-client/"),
            })

        self.assertEqual(response.status_code, 200)
        # Le compte doit etre cree.
        self.assertTrue(Client.objects.filter(numero="612000001").exists())
        env.assert_called_once()
        self.assertEqual(
            env.call_args.kwargs["email_destinataire"], "awa@test.com"
        )

    def test_inscription_client_reussit_meme_si_email_echoue(self):
        """Un email non parti ne doit jamais bloquer l'inscription."""
        from unittest import mock

        with mock.patch("core.views.email_bienvenue_client",
                        side_effect=Exception("Resend indisponible")):
            response = self.client.post("/inscription-client/", {
                "nom": "Awa Diallo",
                "numero": "612000002",
                "ville": "Conakry",
                "email": "awa2@test.com",
                "mot_de_passe": "motdepasse123",
                "confirmer_mot_de_passe": "motdepasse123",
                "captcha_answer": captcha_pour(
                    self.client, "/inscription-client/"),
            })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Client.objects.filter(numero="612000002").exists())

    # ---------- Inscription vendeur ----------

    def test_inscription_vendeur_envoie_un_email_au_vendeur(self):
        from unittest import mock

        with mock.patch("core.views.email_bienvenue_vendeur") as env:
            env.return_value = {"envoye": True, "transport": "resend",
                                "erreur": None}
            response = self.client.post("/inscription-vendeur/", {
                "nom_boutique": "Boutique Test",
                "numero": "622000001",
                "ville": "Conakry",
                "email": "boutique@test.com",
                "mot_de_passe": "motdepasse123",
                "confirmer_mot_de_passe": "motdepasse123",
                "captcha_answer": captcha_pour(
                    self.client, "/inscription-vendeur/"),
            })

        self.assertEqual(response.status_code, 200)
        env.assert_called_once()
        self.assertEqual(
            env.call_args.kwargs["email_destinataire"], "boutique@test.com"
        )

    def test_inscription_vendeur_reussit_meme_si_email_echoue(self):
        from unittest import mock

        with mock.patch("core.views.email_bienvenue_vendeur",
                        side_effect=Exception("Resend indisponible")):
            response = self.client.post("/inscription-vendeur/", {
                "nom_boutique": "Boutique Test 2",
                "numero": "622000002",
                "ville": "Conakry",
                "email": "boutique2@test.com",
                "mot_de_passe": "motdepasse123",
                "confirmer_mot_de_passe": "motdepasse123",
                "captcha_answer": captcha_pour(
                    self.client, "/inscription-vendeur/"),
            })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Vendeur.objects.filter(numero="622000002").exists())

    # ---------- Mot de passe oublie / code ----------

    def test_mot_de_passe_oublie_envoie_le_code(self):
        from unittest import mock

        User.objects.create_user(
            username="oublie@test.com", email="oublie@test.com",
            password="motdepasse123",
        )

        with mock.patch("core.views.email_code_verification") as env:
            env.return_value = {"envoye": True, "transport": "resend",
                                "erreur": None}
            response = self.client.post(
                "/mot-de-passe-oublie/", {"email": "oublie@test.com"}
            )

        self.assertEqual(response.status_code, 200)
        env.assert_called_once()
        # Le code envoye doit correspondre a celui stocke en base.
        code_envoye = env.call_args.kwargs["code"]
        self.assertTrue(
            PasswordResetCode.objects.filter(code=code_envoye).exists()
        )

    def test_mot_de_passe_oublie_affiche_erreur_si_envoi_echoue(self):
        """Ici l'utilisateur est bloque : l'echec doit etre visible."""
        from unittest import mock

        User.objects.create_user(
            username="bloque@test.com", email="bloque@test.com",
            password="motdepasse123",
        )

        with mock.patch("core.views.email_code_verification",
                        side_effect=Exception("SMTP indisponible")):
            response = self.client.post(
                "/mot-de-passe-oublie/", {"email": "bloque@test.com"}
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Impossible d")

    def test_resend_verification_code_renvoie_un_nouveau_code(self):
        from unittest import mock

        User.objects.create_user(
            username="renvoi@test.com", email="renvoi@test.com",
            password="motdepasse123",
        )

        with mock.patch("core.views.email_code_verification") as env:
            env.return_value = {"envoye": True, "transport": "resend",
                                "erreur": None}
            response = self.client.post(
                "/resend-verification-code/", {"email": "renvoi@test.com"}
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        env.assert_called_once()

    def test_resend_verification_code_signale_echec(self):
        from unittest import mock

        with mock.patch("core.views.email_code_verification",
                        side_effect=Exception("SMTP indisponible")):
            response = self.client.post(
                "/resend-verification-code/", {"email": "inconnu@test.com"}
            )

        self.assertFalse(response.json()["success"])

    # ---------- Contenu des emails du service ----------

    def test_email_code_verification_contient_le_code(self):
        from unittest import mock

        with mock.patch("resend.Emails.send", return_value={"id": "x"}) as m:
            with self.settings(RESEND_API_KEY="re_test_123",
                               RESEND_FROM_EMAIL="onboarding@resend.dev",
                               RESEND_FROM_NAME="SHOPY",
                               RESEND_ENABLED=True):
                email_code_verification("client@test.com", "123456")

        params = m.call_args[0][0]
        self.assertIn("123456", params["text"])

    def test_email_bienvenue_client_signale_echec_a_l_appelant(self):
        """Un email de compte ne doit pas echouer silencieusement."""
        from unittest import mock

        with mock.patch("resend.Emails.send",
                        side_effect=Exception("echec")):
            with self.settings(RESEND_API_KEY="re_test_123",
                               RESEND_FROM_EMAIL="onboarding@resend.dev",
                               RESEND_FROM_NAME="SHOPY",
                               RESEND_ENABLED=True):
                with self.assertRaises(Exception):
                    email_bienvenue_client("Awa", "awa@test.com")

class NotificationDismissalTests(TestCase):
    """
    Fermeture des notifications (croix).

    Regression : la croix ne faisait que `remove()` en DOM. La
    notification restait `lue=False` en base, donc elle reapparaisait
    au chargement suivant et a chaque cycle de polling.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="notif-test",
            email="notif-test@test.com",
            password="testpass123",
        )
        self.client.force_login(self.user)

    def test_croix_marque_la_notification_comme_lue(self):
        notif = Notification.objects.create(
            user=self.user, type="commande",
            titre="Nouvelle commande", message="Vous avez une commande",
        )
        self.assertFalse(notif.lue)

        response = self.client.post(
            f"/api/notifications/{notif.pk}/marquer-lue/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["succes"])
        notif.refresh_from_db()
        self.assertTrue(notif.lue, "La notification doit etre marquee lue")

    def test_notification_lue_nest_plus_renvoyee_par_lapi(self):
        """Une notification fermee ne doit plus revenir au polling."""
        notif = Notification.objects.create(
            user=self.user, type="commande",
            titre="Nouvelle commande", message="Vous avez une commande",
        )
        self.client.post(f"/api/notifications/{notif.pk}/marquer-lue/")

        data = self.client.get("/api/notifications/nouvelles/").json()
        self.assertIn("nouvelles", data)
        ids = [n["id"] for n in data["nouvelles"]]
        self.assertNotIn(notif.pk, ids)

    def test_notification_lue_napparait_plus_dans_le_contexte(self):
        """Les toasts du chargement de page doivent ignorer les fermees."""
        notif = Notification.objects.create(
            user=self.user, type="commande",
            titre="Nouvelle commande", message="Vous avez une commande",
        )
        self.client.post(f"/api/notifications/{notif.pk}/marquer-lue/")

        response = self.client.get("/catalogue/")
        toasts = json.loads(response.context["notifications_toast"])
        ids = [n.get("id") for n in toasts]
        self.assertNotIn(notif.pk, ids)

    def test_notification_non_lue_est_bien_exposee_avec_son_id(self):
        """Le JS a besoin de l'id pour marquer la bonne notification."""
        notif = Notification.objects.create(
            user=self.user, type="commande",
            titre="Nouvelle commande", message="Vous avez une commande",
        )
        response = self.client.get("/catalogue/")
        toasts = json.loads(response.context["notifications_toast"])
        ids = [n.get("id") for n in toasts]
        self.assertIn(notif.pk, ids)

    def test_la_reponse_renvoie_le_nombre_de_non_lues(self):
        """Le badge doit se mettre a jour sans attendre le polling."""
        for i in range(3):
            Notification.objects.create(
                user=self.user, type="commande",
                titre=f"Commande {i}", message="Message",
            )
        notif = Notification.objects.filter(lue=False).first()

        data = self.client.post(
            f"/api/notifications/{notif.pk}/marquer-lue/"
        ).json()

        self.assertEqual(data["nb_non_lues"], 2)

    def test_impossible_de_fermer_la_notification_dun_autre(self):
        """Pas de fuite : on ne marque que ses propres notifications."""
        autre = User.objects.create_user(
            username="notif-autre", email="autre@test.com",
            password="testpass123",
        )
        notif_autre = Notification.objects.create(
            user=autre, type="commande",
            titre="Commande privee", message="Confidentiel",
        )

        data = self.client.post(
            f"/api/notifications/{notif_autre.pk}/marquer-lue/"
        ).json()

        self.assertTrue(data["succes"])
        self.assertEqual(data["modifie"], 0, "Ne doit rien modifier")
        notif_autre.refresh_from_db()
        self.assertFalse(notif_autre.lue, "Doit rester non lue")

    def test_utilisateur_anonyme_refuse(self):
        self.client.logout()
        notif = Notification.objects.create(
            user=self.user, type="commande",
            titre="Commande", message="Message",
        )
        response = self.client.post(
            f"/api/notifications/{notif.pk}/marquer-lue/"
        )
        self.assertEqual(response.status_code, 403)


class VendorSettingsSyncTests(TestCase):
    """
    Parametres vendeur : les modifications doivent se propager
    partout, y compris a la page de connexion.

    Regression : `nom_boutique` n'etait ecrit que sur le modele
    Vendeur. Or la connexion vendeur s'authentifie avec
    `User.username` : renommer une boutique rendait donc impossible
    de se reconnecter avec le nouveau nom.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="Boutique Ancienne",
            email="vendeur@test.com",
            password="testpass123",
        )
        self.vendeur = Vendeur.objects.create(
            user=self.user,
            nom_boutique="Boutique Ancienne",
            numero="611000111",
            ville="Conakry",
            statut="actif",
        )
        self.client.force_login(self.user)

    def test_renommer_la_boutique_met_a_jour_le_username(self):
        response = self.client.post(reverse("parametres_vendeur"), {
            "nom_boutique": "Boutique Nouvelle",
            "numero": "611000111",
            "ville": "Conakry",
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.vendeur.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.vendeur.nom_boutique, "Boutique Nouvelle")
        # C'est ce qui manquait : sans cela, connexion-vendeur echouait.
        self.assertEqual(self.user.username, "Boutique Nouvelle")

    def test_le_nouveau_nom_fonctionne_dans_la_connexion(self):
        """Le nom modifie doit etre accepte a la connexion vendeur."""
        self.client.post(reverse("parametres_vendeur"), {
            "nom_boutique": "Boutique Renommee",
            "numero": "611000111",
            "ville": "Conakry",
        })
        self.client.logout()

        response = self.client.post(reverse("connexion_vendeur"), {
            "nom_boutique": "Boutique Renommee",
            "mot_de_passe": "testpass123",
        })

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("dashboard_vendeur"), response["Location"])

    def test_modifier_numero_et_ville_est_bien_applique(self):
        self.client.post(reverse("parametres_vendeur"), {
            "nom_boutique": "Boutique Ancienne",
            "numero": "622999888",
            "ville": "Nzerekore",
        })

        self.vendeur.refresh_from_db()
        self.assertEqual(self.vendeur.numero, "622999888")
        self.assertEqual(self.vendeur.ville, "Nzerekore")

    def test_refuse_un_nom_deja_utilise_par_un_autre_compte(self):
        User.objects.create_user(
            username="Boutique Occupee", email="autre@test.com",
            password="testpass123",
        )

        self.client.post(reverse("parametres_vendeur"), {
            "nom_boutique": "Boutique Occupee",
            "numero": "611000111",
            "ville": "Conakry",
        })

        self.vendeur.refresh_from_db()
        self.user.refresh_from_db()
        # Rien ne doit avoir bouge.
        self.assertEqual(self.vendeur.nom_boutique, "Boutique Ancienne")
        self.assertEqual(self.user.username, "Boutique Ancienne")

    def test_le_nom_avec_espaces_est_preserve(self):
        self.client.post(reverse("parametres_vendeur"), {
            "nom_boutique": "  Ma Belle Boutique  ",
            "numero": "611000111",
            "ville": "Conakry",
        })

        self.user.refresh_from_db()
        # Les espaces sont normalses pour ne pas casser la connexion.
        self.assertEqual(self.user.username, "Ma Belle Boutique")


class ModeEmploiTests(TestCase):
    """La section « creer ma boutique » ne s'affiche que si besoin."""

    def test_un_visiteur_non_connecte_voit_la_section(self):
        response = self.client.get(reverse("mode_emploi"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Créer son compte vendeur")

    def test_un_client_voit_la_section(self):
        Client.objects.create(
            user=User.objects.create_user(
                username="client-guide", email="c@test.com",
                password="testpass123",
            ),
            nom="Client", numero="611111111", ville="Conakry",
        )
        self.client.force_login(
            User.objects.get(username="client-guide")
        )

        response = self.client.get(reverse("mode_emploi"))
        # Un client n'a pas de boutique : la section reste utile.
        self.assertContains(response, "Créer son compte vendeur")

    def test_un_vendeur_existant_ne_voit_plus_la_section(self):
        user = User.objects.create_user(
            username="vendeur-guide", email="v@test.com",
            password="testpass123",
        )
        Vendeur.objects.create(
            user=user, nom_boutique="Boutique Guide",
            numero="611222222", ville="Conakry", statut="actif",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("mode_emploi"))

        self.assertEqual(response.status_code, 200)
        # Il a deja une boutique : inutile de lui proposer d'en creer une.
        self.assertNotContains(response, "Créer son compte vendeur")
        self.assertNotContains(response, "Créer ma boutique")
        # Le reste du guide vendeur reste disponible.
        self.assertContains(response, "Ajouter un produit")


class WelcomePersonalisationTests(TestCase):
    """
    Affichage conditionnel des cartes de la page d'accueil.

    Le comportement est pilote par WELCOME_PERSONNALISE :
      - False (defaut) : les 4 cartes restent visibles, pratique en
        developpement pour tester chaque parcours en un clic.
      - True  : un utilisateur deja inscrit ne voit que l'acces
        correspondant a son role.
    """

    def _creer_client(self, username="w-cli", email="w-cli@t.com"):
        user = User.objects.create_user(
            username=username, email=email, password="testpass123"
        )
        Client.objects.create(
            user=user, nom="Test", numero="611000444", ville="Conakry"
        )
        return user

    def _creer_vendeur(self, username="w-ven", email="w-ven@t.com"):
        user = User.objects.create_user(
            username=username, email=email, password="testpass123"
        )
        Vendeur.objects.create(
            user=user, nom_boutique="Boutique Test",
            numero="611000555", ville="Conakry", statut="actif",
        )
        return user

    # ---------- Mode developpement (defaut) ----------

    @override_settings(WELCOME_PERSONNALISE=False)
    def test_mode_dev_affiche_les_quatre_cartes(self):
        response = self.client.get(reverse("Welcome"))
        self.assertEqual(response.status_code, 200)
        # Libelles propres a la carte d'accueil (mode developpement).
        self.assertContains(response, "Gerer ma boutique et mes produits")
        self.assertContains(response, "Suivre mes commandes et favoris")
        self.assertContains(response, "Creer ma boutique et poster mes articles")
        self.assertNotContains(response, "Mon Espace Vendeur")

    @override_settings(WELCOME_PERSONNALISE=False)
    def test_mode_dev_garde_les_cartes_meme_pour_un_client(self):
        """En developpement on doit pouvoir tout tester en un clic."""
        user = self._creer_client()
        self.client.force_login(user)

        response = self.client.get(reverse("Welcome"))
        # Les 4 cartes restent : rien ne doit disparaitre en dev.
        self.assertContains(response, "Gerer ma boutique et mes produits")
        self.assertContains(response, "Suivre mes commandes et favoris")
        self.assertNotContains(response, "Mon Espace Vendeur")

    # ---------- Mode personnalise ----------

    @override_settings(WELCOME_PERSONNALISE=True)
    def test_visiteur_non_connecte_voit_toujours_les_cartes(self):
        response = self.client.get(reverse("Welcome"))
        # Sans compte, on propose les parcours d'inscription/connexion.
        self.assertContains(response, "Creer ma boutique et poster mes articles")
        self.assertContains(response, "Acceder a mon compte client")
        # Pas de compte : on ne peut pas proposer un espace perso.
        self.assertNotContains(response, "Mon Espace Vendeur")

    @override_settings(WELCOME_PERSONNALISE=True)
    def test_un_client_voit_son_compte_mais_pas_les_offres_vendeur(self):
        user = self._creer_client()
        self.client.force_login(user)

        response = self.client.get(reverse("Welcome"))

        self.assertContains(response, "Suivre mes commandes et favoris")
        # Un client n'a pas a « se reconnecter » : c'est contradictoire.
        # On cible la carte, pas les liens du menu / pied de page qui
        # restent la navigation du site.
        self.assertNotContains(
            response, reverse("connexion_client") + '" class="choice-card'
        )
        self.assertNotContains(
            response, reverse("connexion_vendeur") + '" class="choice-card'
        )
        # Il peut en revanche devenir vendeur : l'offre reste affichee,
        # car un client peut parfaitement creer une boutique par la suite.
        self.assertContains(response, "Creer ma boutique et poster mes articles")

    @override_settings(WELCOME_PERSONNALISE=True)
    def test_un_vendeur_voit_son_espace_pas_la_connexion(self):
        user = self._creer_vendeur()
        self.client.force_login(user)

        response = self.client.get(reverse("Welcome"))

        self.assertContains(response, "Mon Espace Vendeur")
        # Cible la carte, pas les liens du menu / pied de page.
        self.assertNotContains(response, reverse("connexion_vendeur") + '" class="choice-card')
        # Il a deja une boutique : ne pas lui proposer d'en creer une.
        self.assertNotContains(response, "Creer ma boutique et poster mes articles")
        # « Acheter » reste accessible a tout le monde.
        self.assertContains(response, "Acheter")

    @override_settings(WELCOME_PERSONNALISE=True)
    def test_le_client_peut_toujours_acheter(self):
        """Le catalogue ne doit jamais etre masque."""
        user = self._creer_client()
        self.client.force_login(user)

        response = self.client.get(reverse("Welcome"))
        self.assertContains(response, reverse("catalogue"))

    @override_settings(WELCOME_PERSONNALISE=True)
    def test_un_double_compte_voit_les_deux_acces(self):
        """
        Cas reel : la connexion client privilegie le profil Client et le
        projet gere le cas ou un utilisateur a les deux roles.
        Les deux acces doivent alors etre proposes.
        """
        user = self._creer_client(username="w-duo", email="w-duo@t.com")
        Vendeur.objects.create(
            user=user, nom_boutique="Duo",
            numero="611000666", ville="Conakry", statut="actif",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("Welcome"))

        self.assertContains(response, "Mon Espace Vendeur")
        self.assertContains(response, "Suivre mes commandes et favoris")
        # Aucune connexion ni creation : il a deja les deux comptes.
        self.assertNotContains(response, reverse("connexion_vendeur") + '" class="choice-card')
        self.assertNotContains(response, "Creer ma boutique et poster mes articles")


class CaptchaInscriptionTests(TestCase):
    """
    Verification anti-robot (« Verification de securite ») des deux
    formulaires d'inscription.

    Garanties attendues : la question s'affiche vraiment, la reponse
    attendue reste en session (jamais dans le HTML), une mauvaise
    reponse interdit la creation du compte, et chaque essai consomme
    la reponse (usage unique).
    """

    # ---------- Utilitaires ----------

    def _question_affichee(self, url):
        """Retourne la question CAPTCHA telle qu'elle apparait a l'ecran."""
        html = self.client.get(url).content.decode("utf-8")
        trouve = re.search(r'id="captcha-question">([^<]*)<', html)
        return trouve.group(1).strip() if trouve else ""

    def _resoudre(self, question):
        """Resout « 7 + 4 = ? » pour fournir une reponse correcte."""
        corps = question.replace("=", "").replace("?", "").strip()
        for operateur in ("+", "-", "x"):
            if operateur in corps:
                a, b = [int(v.strip()) for v in corps.split(operateur)]
                return {"+": a + b, "-": a - b, "x": a * b}[operateur]
        raise AssertionError("Question CAPTCHA illisible : " + question)

    def _donnees_client(self, **kwargs):
        donnees = {
            "nom": "Awa Diallo",
            "numero": "612000001",
            "ville": "Conakry",
            "email": "captcha.client@test.com",
            "mot_de_passe": "motdepasse123",
            "confirmer_mot_de_passe": "motdepasse123",
        }
        donnees.update(kwargs)
        return donnees

    def _donnees_vendeur(self, **kwargs):
        donnees = {
            "nom_boutique": "Boutique Captcha",
            "numero": "622000001",
            "ville": "Conakry",
            "email": "captcha.vendeur@test.com",
            "mot_de_passe": "motdepasse123",
            "confirmer_mot_de_passe": "motdepasse123",
        }
        donnees.update(kwargs)
        return donnees

    # ---------- La question s'affiche vraiment ----------

    def test_la_question_s_affiche_sur_le_formulaire_client(self):
        question = self._question_affichee(reverse("inscription_client"))
        self.assertTrue(question, "La question ne doit pas etre vide")
        self.assertIn("=", question)

    def test_la_question_s_affiche_sur_le_formulaire_vendeur(self):
        question = self._question_affichee(reverse("inscription_vendeur"))
        self.assertTrue(question, "La question ne doit pas etre vide")
        self.assertIn("=", question)

    def test_chaque_visite_propose_une_question_neuve(self):
        url = reverse("inscription_client")
        questions = {self._question_affichee(url) for _ in range(12)}
        self.assertGreater(
            len(questions), 1,
            "Les questions doivent varier d'une visite a l'autre")

    # ---------- Le CAPTCHA bloque reellement ----------

    def test_reponse_fausse_interdit_la_creation_du_compte(self):
        url = reverse("inscription_client")
        self.client.get(url)
        reponse = self.client.post(
            url, self._donnees_client(captcha_answer="999999"))
        self.assertContains(reponse, "incorrecte")
        self.assertFalse(
            User.objects.filter(username="captcha.client@test.com").exists())

    def test_reponse_absente_interdit_la_creation_du_compte(self):
        url = reverse("inscription_client")
        self.client.get(url)
        self.client.post(url, self._donnees_client())
        self.assertFalse(Client.objects.exists())

    def test_reponse_correcte_cree_le_compte(self):
        url = reverse("inscription_client")
        question = self._question_affichee(url)
        self.client.post(url, self._donnees_client(
            captcha_answer=str(self._resoudre(question))))
        self.assertTrue(Client.objects.filter(numero="612000001").exists())

    def test_vendeur_reponse_fausse_interdit_la_creation(self):
        url = reverse("inscription_vendeur")
        self.client.get(url)
        self.client.post(
            url, self._donnees_vendeur(captcha_answer="999999"))
        self.assertFalse(Vendeur.objects.exists())

    def test_vendeur_reponse_correcte_cree_la_boutique(self):
        url = reverse("inscription_vendeur")
        question = self._question_affichee(url)
        self.client.post(url, self._donnees_vendeur(
            captcha_answer=str(self._resoudre(question))))
        self.assertTrue(Vendeur.objects.filter(numero="622000001").exists())

    # ---------- Usage unique ----------

    def test_la_reponse_est_consommee_et_ne_peut_pas_etre_rejouee(self):
        url = reverse("inscription_client")
        question = self._question_affichee(url)
        bonne = str(self._resoudre(question))
        self.client.post(url, self._donnees_client(captcha_answer=bonne))
        self.assertTrue(Client.objects.filter(numero="612000001").exists())

        # Meme session, meme reponse, autre email : doit etre refuse.
        self.client.post(url, self._donnees_client(
            numero="612000999", email="rejeu.captcha@test.com",
            captcha_answer=bonne))
        self.assertFalse(
            Client.objects.filter(numero="612000999").exists(),
            "Rejouer la meme reponse ne doit pas fonctionner")

    def test_une_question_neuve_est_fournie_apres_un_echec(self):
        url = reverse("inscription_client")
        self.client.get(url)
        reponse = self.client.post(
            url, self._donnees_client(captcha_answer="999999"))
        html = reponse.content.decode("utf-8")
        trouve = re.search(r'id="captcha-question">([^<]*)<', html)
        self.assertTrue(trouve and trouve.group(1).strip(),
                        "Une question neuve doit suivre un echec")

    # ---------- Bouton « Nouvelle question » ----------

    def test_le_bouton_nouvelle_question_renvoie_une_question(self):
        reponse = self.client.get(reverse("renouveler_captcha"))
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.json().get("question"))

    def test_la_question_du_bouton_est_utilisable(self):
        """La question renvoyee doit permettre de creer un compte."""
        url = reverse("inscription_client")
        question = self.client.get(
            reverse("renouveler_captcha")).json()["question"]
        self.client.post(url, self._donnees_client(
            captcha_answer=str(self._resoudre(question))))
        self.assertTrue(Client.objects.filter(numero="612000001").exists())

    def test_le_bouton_refuse_les_methodes_autres_que_get(self):
        self.assertEqual(
            self.client.post(reverse("renouveler_captcha")).status_code, 405)

    # ---------- La reponse ne doit pas fuir dans le HTML ----------

    def test_la_reponse_attendue_vit_en_session_pas_dans_le_html(self):
        """
        Un champ cache serait lisible par un robot : la reponse doit
        rester cote serveur, dans la session.
        """
        url = reverse("inscription_client")
        html = self.client.get(url).content.decode("utf-8")
        self.assertIsNotNone(self.client.session.get(CLE_CAPTCHA_SESSION))
        self.assertIn('name="captcha_answer"', html)
        self.assertNotIn('type="hidden" name="captcha', html)


class InscriptionClientValidationTests(TestCase):
    """
    Validation des champs du formulaire d'inscription client.

    Regle : chaque champ doit respecter son format. Le numero
    WhatsApp n'accepte QUE des chiffres (le + et les separateurs
    de lecture sont toleres puis nettoyes).
    """

    def _post(self, **kwargs):
        donnees = {
            "nom": "Awa Diallo",
            "numero": "612000001",
            "ville": "Conakry",
            "email": "awa.validation@test.com",
            "mot_de_passe": "motdepasse123",
            "confirmer_mot_de_passe": "motdepasse123",
            # Le CAPTCHA est obligatoire : on repond correctement pour
            # que ces tests portent bien sur la validation des champs.
            "captcha_answer": captcha_pour(
                self.client, reverse("inscription_client")),
        }
        donnees.update(kwargs)
        return self.client.post(reverse("inscription_client"), data=donnees)

    # ---------- Numero : chiffres uniquement ----------

    def test_numero_valide_cree_le_compte(self):
        self.assertEqual(self._post().status_code, 200)
        self.assertTrue(Client.objects.filter(numero="612000001").exists())

    def test_numero_avec_lettres_est_refuse(self):
        self._post(numero="61200000abc")
        self.assertFalse(Client.objects.exists())
        self.assertContains(self._post(numero="61200000abc"), "chiffres")

    def test_numero_avec_symboles_est_refuse(self):
        for numero in ("612/000/001", "612#000#001", "612@000@001",
                       "612*000", "abc12345678", "612_000_001"):
            with self.subTest(numero=numero):
                Client.objects.all().delete()
                self._post(numero=numero)
                self.assertFalse(
                    Client.objects.exists(),
                    "Le numero {0} aurait du etre refuse".format(numero),
                )

    def test_espaces_et_plus_sont_acceptes_et_nettoyes(self):
        """Le +224 et les espaces sont une saisie legitime."""
        self._post(numero="+224 612 00 00 01")
        self.assertTrue(
            Client.objects.filter(numero="224612000001").exists()
        )

    def test_points_et_tirets_sont_acceptes(self):
        self._post(numero="612.00.00.01")
        self.assertTrue(Client.objects.filter(numero="612000001").exists())

    def test_numero_trop_court_ou_vide_est_refuse(self):
        self._post(numero="12345")
        self.assertFalse(Client.objects.exists())
        self._post(numero="")
        self.assertFalse(Client.objects.exists())

    # ---------- Email ----------

    def test_email_invalide_est_refuse(self):
        for email in ("pasunemail", "awa@", "@test.com", "awa test@test.com"):
            with self.subTest(email=email):
                Client.objects.all().delete()
                self._post(email=email)
                self.assertFalse(
                    Client.objects.exists(),
                    "L'email {0} aurait du etre refuse".format(email),
                )

    # ---------- Nom et ville ----------

    def test_nom_ou_ville_vide_est_refuse(self):
        self._post(nom="   ")
        self.assertFalse(Client.objects.exists())
        self._post(ville="")
        self.assertFalse(Client.objects.exists())

    def test_nom_est_normalise_aux_espaces(self):
        self._post(nom="  Awa Diallo  ")
        self.assertTrue(Client.objects.filter(nom="Awa Diallo").exists())

    # ---------- Mot de passe ----------

    def test_mot_de_passe_trop_court_ou_non_confirme_est_refuse(self):
        self._post(mot_de_passe="court", confirmer_mot_de_passe="court")
        self.assertFalse(Client.objects.exists())
        self._post(confirmer_mot_de_passe="autre123456")
        self.assertFalse(Client.objects.exists())

    def test_email_deja_utilise_ne_cree_pas_un_second_profil(self):
        self._post()
        self.assertTrue(Client.objects.exists())
        Client.objects.all().delete()
        # Le compte User existe deja : pas de second profil Client.
        self._post(email="awa.validation@test.com", numero="622000002")
        self.assertEqual(Client.objects.count(), 0)


class ValidatorsUnitTests(TestCase):
    """Tests directs de core/validators.py (sans passer par la vue)."""

    def test_nettoyer_telephone_accepte_les_separateurs(self):
        from .validators import nettoyer_telephone

        self.assertEqual(nettoyer_telephone("+224 612 00 00 01"),
                         "224612000001")
        self.assertEqual(nettoyer_telephone("612.00.00.01"), "612000001")
        self.assertEqual(nettoyer_telephone("(612) 00-00-01"), "612000001")

    def test_nettoyer_telephone_refuse_lettres_et_symboles(self):
        from django.core.exceptions import ValidationError
        from .validators import nettoyer_telephone

        for valeur in ("61200000abc", "612#000", "612@000", "612$000"):
            with self.subTest(valeur=valeur):
                with self.assertRaises(ValidationError):
                    nettoyer_telephone(valeur)

    def test_email_vide_ou_invalide(self):
        from django.core.exceptions import ValidationError
        from .validators import validate_email

        self.assertEqual(validate_email("a@b.com"), "a@b.com")
        for valeur in ("", "  ", "abc", "a@b", "a b@c.com"):
            with self.subTest(valeur=valeur):
                with self.assertRaises(ValidationError):
                    validate_email(valeur)

    def test_texte_non_vide(self):
        from django.core.exceptions import ValidationError
        from .validators import validate_texte_non_vide

        self.assertEqual(validate_texte_non_vide("  Awa  ", "Le nom"), "Awa")
        with self.assertRaises(ValidationError):
            validate_texte_non_vide("   ", "Le nom")


class TemplateCompilationTests(TestCase):
    """Chaque template doit compiler : un {% block %} non fermé casse toute la page."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="vendor-template-compile",
            email="vendor-template-compile@test.com",
            password="testpass123",
        )
        Vendeur.objects.create(
            user=self.user,
            nom_boutique="Boutique Templates",
            numero="+224600000080",
            ville="Conakry",
            statut="actif",
        )
        self.client.force_login(self.user)

    def test_tous_les_templates_du_projet_compilent(self):
        import glob
        import os

        from django.template import engines

        engine = engines["django"]
        fichiers = sorted(glob.glob("core/templates/core/*.html"))
        self.assertGreater(len(fichiers), 0, "Aucun template de core n'a ete trouve")

        erreurs = []
        for chemin in fichiers:
            nom = "core/" + os.path.basename(chemin)
            try:
                engine.get_template(nom)
            except Exception as exc:  # noqa: BLE001 - on rapporte tout probleme
                erreurs.append("{0} :: {1}".format(nom, exc))

        self.assertEqual(erreurs, [], "Templates invalides :\n" + "\n".join(erreurs))

    def test_page_chat_assistant_ia_rend_correctement(self):
        """Regression : {% block content %} non ferme levait une TemplateSyntaxError (500)."""
        response = self.client.get(reverse("assistant_ia_chat"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "chatMessages")
        self.assertContains(response, "sendMessage")


class VendorNavigationAndProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="vendor-navigation-test",
            email="vendor-navigation-test@test.com",
            password="testpass123",
        )
        Vendeur.objects.create(
            user=self.user,
            nom_boutique="Boutique Navigation",
            numero="+224600000070",
            ville="Conakry",
            statut="actif",
        )
        self.client.force_login(self.user)

    def test_vendor_navigation_has_only_five_requested_items_and_no_messages(self):
        response = self.client.get(reverse("dashboard_vendeur"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        nav = html.split('<nav class="SHOPY-bottom-nav">', 1)[1].split('</nav>', 1)[0]
        labels = [
            part.split("</span>", 1)[0]
            for part in nav.split('<span class="SHOPY-nav-label">')[1:]
        ]
        self.assertEqual(labels, ["Boutique", "Commandes", "Produits", "Marketplace"])
        self.assertIn("SHOPY-nav-center-item", nav)
        self.assertNotIn("messages_vendeur", nav)

    def test_vendor_profile_uses_shared_profile_stylesheet_on_dashboard(self):
        response = self.client.get(reverse("dashboard_vendeur"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "vendor-header")
        self.assertContains(response, "dashboard-header-premium")

    def test_ajouter_produit_uses_shared_vendor_header_and_navigation(self):
        response = self.client.get(reverse("ajouter_produit"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode("utf-8")
        self.assertIn("dashboard-header-premium", html)
        self.assertIn("product-form-anti-ia", html)
        self.assertIn("SHOPY-bottom-nav", html)
        self.assertNotIn("messages_vendeur", html.split('<nav class="SHOPY-bottom-nav">', 1)[1].split('</nav>', 1)[0])



class FavorisTests(TestCase):
    def test_csrf_cookie_is_readable_by_javascript_for_ajax_favorites(self):
        self.assertFalse(settings.CSRF_COOKIE_HTTPONLY)

    def test_hidden_product_is_not_shown_in_client_favorites(self):
        user = User.objects.create_user(
            username="client-favoris-hidden",
            email="client-favoris-hidden@test.com",
            password="testpass123",
        )
        client = Client.objects.create(
            user=user,
            nom="Client Favoris",
            numero="+224600000040",
            ville="Conakry",
        )
        vendeur = Vendeur.objects.create(
            user=User.objects.create_user(
                username="vendeur-favoris-hidden",
                email="vendeur-favoris-hidden@test.com",
                password="testpass123",
            ),
            nom_boutique="Boutique cachée",
            numero="+224600000041",
            ville="Conakry",
            statut="actif",
        )
        categorie = Categorie.objects.create(nom="Test", slug="test-hidden", icone="📦")
        produit = Produit.objects.create(
            vendeur=vendeur,
            nom="Produit caché",
            photo="produits/hidden.jpg",
            prix=15000,
            quantite=2,
            description="Produit non visible",
            categorie=categorie,
            visible=False,
        )
        Favori.objects.create(client=client, produit=produit)

        self.client.force_login(user)
        response = self.client.get(reverse("mes_favoris"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["favoris"]), 0)
        self.assertNotContains(response, "Produit caché")


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


class PromotionsCoherenceTests(TestCase):
    """La promotion affichée doit toujours être réelle (prix promo valide)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="promo-vendeur",
            password="testpass123",
            email="promo-vendeur@test.com",
        )
        self.vendeur = Vendeur.objects.create(
            user=self.user,
            nom_boutique="Promo Boutique",
            numero="+224600000099",
            ville="Conakry",
            statut="actif",
        )
        self.categorie = Categorie.objects.create(nom="Mode", slug="mode")
        plan, _ = PlanAbonnement.objects.get_or_create(
            nom="gratuit",
            defaults={"prix": 0, "limite_produits": 5, "duree_jours": 30},
        )
        Abonnement.objects.get_or_create(
            vendeur=self.vendeur,
            defaults={
                "plan": plan,
                "statut": "essai",
                "date_fin": timezone.now() + timedelta(days=30),
            },
        )

    def test_promo_sans_prix_promo_est_refusee(self):
        from .forms import ProduitForm

        form = ProduitForm(data={
            "nom": "Produit test",
            "prix": "10000",
            "quantite": "5",
            "description": "desc",
            "categorie": self.categorie.pk,
            "promo": "on",
        })

        self.assertFalse(form.is_valid())
        self.assertIn("prix_promo", form.errors)

    def test_promo_avec_prix_inferieur_est_acceptee(self):
        from .forms import ProduitForm

        form = ProduitForm(data={
            "nom": "Produit test",
            "prix": "10000",
            "quantite": "5",
            "description": "desc",
            "categorie": self.categorie.pk,
            "promo": "on",
            "prix_promo": "8000",
            "jours_promo": "7",
        })

        self.assertTrue(form.is_valid(), form.errors)

    def test_produit_incoherent_n_apparait_pas_dans_l_onglet_promo(self):
        Produit.objects.create(
            vendeur=self.vendeur,
            nom="Produit incohérent",
            photo="produits/incoherent.jpg",
            prix=10000,
            quantite=1,
            description="promo sans prix",
            categorie=self.categorie,
            promo=True,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("liste_produits_vendeur"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["produits_promo"]), [])


class StatistiquesVendeurAffichageTests(TestCase):
    def test_le_statut_des_commandes_n_est_plus_affiche(self):
        user = User.objects.create_user(
            username="stats-vendeur",
            password="testpass123",
        )
        Vendeur.objects.create(
            user=user,
            nom_boutique="Stats Boutique",
            numero="+224600000098",
            ville="Conakry",
            statut="actif",
        )

        self.client.force_login(user)
        response = self.client.get(reverse("statistiques_vendeur"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Analyse des commandes")


class InscriptionVendeurFormuleTests(TestCase):
    def _post_essai(self):
        return self.client.post(reverse("inscription_vendeur"), {
            "nom_boutique": "Boutique Essai",
            "numero": "622000901",
            "ville": "Conakry",
            "email": "essai@test.com",
            "mot_de_passe": "motdepasse123",
            "confirmer_mot_de_passe": "motdepasse123",
            "captcha_answer": captcha_pour(
                self.client, reverse("inscription_vendeur")),
        })

    def test_inscription_par_defaut_commence_en_essai_gratuit(self):
        from unittest import mock

        with mock.patch("core.views.email_bienvenue_vendeur"):
            response = self._post_essai()

        self.assertEqual(response.status_code, 200)
        vendeur = Vendeur.objects.get(nom_boutique="Boutique Essai")
        self.assertFalse(
            PaiementAbonnement.objects.filter(vendeur=vendeur).exists())

    def test_inscription_avec_paiement_cree_un_paiement_en_attente(self):
        from unittest import mock

        plan = PlanAbonnement.objects.create(
            nom="essentiel",
            prix=30000,
            limite_produits=10,
            duree_jours=30,
        )

        with mock.patch("core.views.email_bienvenue_vendeur"):
            response = self.client.post(reverse("inscription_vendeur"), {
                "nom_boutique": "Boutique Payante",
                "numero": "622000902",
                "ville": "Conakry",
                "email": "payante@test.com",
                "mot_de_passe": "motdepasse123",
                "confirmer_mot_de_passe": "motdepasse123",
                "formule": "paiement",
                "plan": "essentiel",
                "numero_paiement": "612345678",
                "reference": "OM123",
                "captcha_answer": captcha_pour(
                    self.client, reverse("inscription_vendeur")),
            })

        self.assertEqual(response.status_code, 200)
        vendeur = Vendeur.objects.get(nom_boutique="Boutique Payante")
        paiement = PaiementAbonnement.objects.get(vendeur=vendeur)
        self.assertEqual(paiement.statut, "en_attente")
        self.assertEqual(paiement.plan, plan)
        self.assertEqual(paiement.montant, 30000)

    def test_page_admin_paiements_affiche_les_infos_du_vendeur(self):
        staff = User.objects.create_user(
            username="admin-paiement-test",
            password="testpass123",
            is_staff=True,
            email="admin-paiement@test.com",
        )
        vendeur = Vendeur.objects.create(
            user=User.objects.create_user(
                username="vendeur-paiement-test",
                password="testpass123",
                email="vendeur-paiement@test.com",
            ),
            nom_boutique="Boutique Payante Admin",
            numero="+224600000097",
            ville="Labé",
            statut="en_attente",
        )
        plan = PlanAbonnement.objects.create(
            nom="pro",
            prix=60000,
            limite_produits=60,
            duree_jours=30,
        )
        PaiementAbonnement.objects.create(
            vendeur=vendeur,
            plan=plan,
            numero_paiement="611111111",
            montant=60000,
            statut="en_attente",
        )

        self.client.force_login(staff)
        response = self.client.get(reverse("admin_paiements"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Boutique Payante Admin")
        self.assertContains(response, "Labé")
        self.assertContains(response, "vendeur-paiement@test.com")


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


class VentesMoisCommandesTests(TestCase):
    """Les ventes mensuelles ne sont comptabilisées qu'une fois, à l'acceptation."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="vendeur-ventes-mois",
            email="vendeur-ventes-mois@test.com",
            password="testpass123",
        )
        self.vendeur = Vendeur.objects.create(
            user=self.user,
            nom_boutique="Boutique Ventes Mensuelles",
            numero="+224600000060",
            ville="Conakry",
            statut="actif",
        )
        self.client_profile = Client.objects.create(
            user=User.objects.create_user(
                username="client-ventes-mois",
                email="client-ventes-mois@test.com",
                password="testpass123",
            ),
            nom="Client Ventes Mensuelles",
            numero="+224600000061",
            ville="Conakry",
        )
        categorie = Categorie.objects.create(
            nom="Test ventes",
            slug="test-ventes-mois",
            icone="📦",
        )
        self.produit = Produit.objects.create(
            vendeur=self.vendeur,
            nom="Produit ventes",
            photo="produits/ventes-mois.jpg",
            prix=25000,
            quantite=10,
            description="Produit pour tester les ventes mensuelles",
            categorie=categorie,
            visible=True,
        )
        self.client.force_login(self.user)

    def _creer_commande_payee(self, paiement_direct=True, montant=25000):
        commande = Commande.objects.create(
            produit=self.produit,
            vendeur=self.vendeur,
            nom_client=self.client_profile.nom,
            numero_client=self.client_profile.numero,
            ville_client=self.client_profile.ville,
            quantite=1,
            prix_unitaire=montant,
            prix_total=montant,
            statut="en_attente",
        )
        if paiement_direct:
            PaiementCommande.objects.create(
                commande=commande,
                numero_paiement="paiement-direct-001",
                montant=montant,
                statut="valide",
            )
        else:
            PaiementPanier.objects.create(
                client=self.client_profile,
                numero_paiement="paiement-panier-001",
                montant_total=montant,
                statut="valide",
            )
            commande.paiement_panier = PaiementPanier.objects.get(
                numero_paiement="paiement-panier-001"
            )
            commande.save(update_fields=["paiement_panier"])
        return commande

    def _accepter(self, commande, follow=False):
        return self.client.post(
            reverse("changer_statut_commande", kwargs={"pk": commande.pk}),
            {"statut": "acceptee"},
            follow=follow,
        )

    def _verifier_ouvrir_avant_acceptation(self):
        for _ in range(3):
            response = self.client.get(reverse("commandes_vendeur"))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["ventes_du_mois"], 0)
        self.vendeur.refresh_from_db()
        self.assertEqual(self.vendeur.ventes_du_mois, 0)

    def test_commande_directe_comptee_une_seule_fois_a_l_acceptation(self):
        commande = self._creer_commande_payee(paiement_direct=True, montant=25000)

        self._verifier_ouvrir_avant_acceptation()

        response = self._accepter(commande, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["ventes_du_mois"], 25000)

        # La redirection vers « Mes commandes » ne doit pas compter la vente une seconde fois.
        self.client.get(reverse("commandes_vendeur"))
        self._accepter(commande, follow=True)
        self.vendeur.refresh_from_db()
        self.assertEqual(self.vendeur.ventes_du_mois, 25000)

    def test_commande_panier_comptee_une_seule_fois_a_l_acceptation(self):
        commande = self._creer_commande_payee(paiement_direct=False, montant=32000)

        self._verifier_ouvrir_avant_acceptation()

        self._accepter(commande, follow=True)
        self.client.get(reverse("commandes_vendeur"))
        self.vendeur.refresh_from_db()
        self.assertEqual(self.vendeur.ventes_du_mois, 32000)



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
