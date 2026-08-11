from django.urls import path, include
from django.shortcuts import render
from rest_framework.routers import DefaultRouter
from . import views
from .views_shopy_features import (
    vendeurs_certifies, demander_certification, noter_vendeur, admin_certifier_vendeur,
    mes_garanties, demander_remboursement, admin_garanties, traiter_garantie,
    flash_sales, detail_flash_sale, creer_flash_sale, acheter_flash_sale, api_flash_sales,
    alertes_prix, creer_alerte, supprimer_alerte, assistant_ia_vendeur, assistant_ia_chat
)
from django.conf import settings
from django.conf.urls.static import static

router = DefaultRouter()
router.register(r'clients', views.ClientViewSet)
router.register(r'vendeurs', views.VendeurViewSet)
router.register(r'produits', views.ProduitViewSet)
router.register(r'commandes', views.CommandeViewSet)
router.register(r'abonnements', views.AbonnementViewSet)
router.register(r'notifications', views.NotificationViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
    
# Page d'accueil
    path('', views.welcome, name='Welcome'),
    
    # Pages légales et contact
    path('cgu/', lambda request: render(request, 'core/cgu.html'), name='cgu'),
    path('confidentialite/', lambda request: render(request, 'core/politique_confidentialite.html'), name='confidentialite'),
    path('cgv/', lambda request: render(request, 'core/cgv.html'), name='cgv'),
    path('contact/', lambda request: render(request, 'core/contact.html'), name='contact'),
    
    # Authentication Vendeur
    path('inscription-vendeur/', views.inscription_vendeur, name='inscription_vendeur'),
    path('connexion-vendeur/', views.connexion_vendeur, name='connexion_vendeur'),
    path('deconnexion/', views.deconnexion_vendeur, name='deconnexion_vendeur'),
    
    # Dashboard Vendeur
    path('mon_espace_vendeur/', views.dashboard_vendeur, name='dashboard_vendeur'),
    path('mes-produits/', views.liste_produits_vendeur, name='liste_produits_vendeur'),
    path('mes-commandes/', views.commandes_vendeur, name='commandes_vendeur'),
    path('mes-parametres/', views.parametres_vendeur, name='parametres_vendeur'),
    path('mes-statistiques/', views.statistiques_vendeur, name='statistiques_vendeur'),
    path('abonnement/', views.abonnement_vendeur, name='abonnement_vendeur'),
    path('messages-vendeur/', views.messages_vendeur, name='messages_vendeur'),
    
    # Gestion Produits
    path('ajouter-produit/', views.ajouter_produit, name='ajouter_produit'),
    path('choisir-photo-produit/', views.choisir_photo_produit, name='choisir_photo_produit'),
    path('set-photo-produit/', views.set_photo_produit, name='set_photo_produit'),
    path('modifier-produit/<int:pk>', views.modifier_produit, name='modifier_produit'),
    path('supprimer-produit/<int:pk>', views.supprimer_produit, name='supprimer_produit'),
    
    # Commandes
    path('commande/<int:pk>/statut/', views.changer_statut_commande, name='changer_statut_commande'),
    path('commande/<int:pk>/annuler/', views.annuler_commande, name='annuler_commande'),
    
    # Abonnement
    path('choisir-abonnement/', views.choisir_abonnement, name='choisir_abonnement'),
    path('payer-abonnement/<str:plan_nom>/', views.payer_abonnement, name='payer_abonnement'),
    path('confirmation-paiement/', views.confirmation_paiement, name='confirmation_paiement'),
    
# Admin
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-vendeurs/', views.admin_vendeurs, name='admin_vendeurs'),
    path('admin-paiements/', views.admin_paiements, name='admin_paiements'),
    path('admin-paiements/<int:pk>/valider/', views.admin_valider_paiement_abonnement, name='admin_valider_paiement_abonnement'),
    path('admin-paiements-commandes/', views.admin_paiements_commandes, name='admin_paiements_commandes'),
    path('admin-vendeur/<int:pk>/action/', views.admin_valider_vendeur, name='admin_valider_vendeur'),
    path('admin-paiement-commande/<int:pk>/valider/', views.admin_valider_paiement_commande, name='admin_valider_paiement_commande'),
    path('admin-signalement/<int:pk>/traiter/', views.admin_traiter_signalement, name='admin_traiter_signalement'),
    path('admin-signalements/', views.admin_signalements, name='admin_signalements'),
    path('admin-certifies/', views.admin_certifies, name='admin_certifies'),
    path('admin-garanties/', views.admin_garanties, name='admin_garanties'),
    
    # === FONCTIONNALITÉS SHOPY ===
    # Vendeurs Certifiés
    path('vendeurs-certifies/', vendeurs_certifies, name='vendeurs_certifies'),
    path('demander-certification/', demander_certification, name='demander_certification'),
    path('vendeur/<int:pk>/noter/', noter_vendeur, name='noter_vendeur'),
    path('admin-certifier/<int:pk>/', admin_certifier_vendeur, name='admin_certifier_vendeur'),
    
    # Garantie Acheteur
    path('mes-garanties/', mes_garanties, name='mes_garanties'),
    path('garantie/<int:pk>/demander-remboursement/', demander_remboursement, name='demander_remboursement'),
    path('admin-garanties/', admin_garanties, name='admin_garanties'),
    path('admin-garantie/<int:pk>/traiter/', traiter_garantie, name='traiter_garantie'),
    
    # Flash Sales
    path('flash-sales/', flash_sales, name='flash_sales'),
    path('flash-sale/<int:pk>/', detail_flash_sale, name='detail_flash_sale'),
    path('creer-flash-sale/', creer_flash_sale, name='creer_flash_sale'),
    path('flash-sale/<int:pk>/acheter/', acheter_flash_sale, name='acheter_flash_sale'),
    path('api/flash-sales/', api_flash_sales, name='api_flash_sales'),
    
# Alertes Prix
    path('alertes-prix/', alertes_prix, name='alertes_prix'),
    path('creer-alerte/', creer_alerte, name='creer_alerte'),
    path('alerte/<int:pk>/supprimer/', supprimer_alerte, name='supprimer_alerte'),
    
# Assistant IA Vendeur
    path('assistant-ia/', assistant_ia_vendeur, name='assistant_ia_vendeur'),
    path('assistant-ia/chat/', assistant_ia_chat, name='assistant_ia_chat'),
    
    # Authentication Client
    path('inscription-client/', views.inscription_client, name='inscription_client'),
    path('connexion-client/', views.connexion_client, name='connexion_client'),
    path('mon-compte/', views.espace_client, name='espace_client'),
    path('mon-compte/parametres/', views.parametres_client, name='parametres_client'),
    path('mon-compte/supprimer-historique/', views.supprimer_historique_commandes_client, name='supprimer_historique_commandes_client'),
    
    # Catalogue & Produits
    path('catalogue/', views.catalogue, name='catalogue'),
    path('produit/<int:pk>/', views.detail_produit, name='detail_produit'),
    path('produit/<int:pk>/Commander/', views.passer_commande, name='passer_commande'),
    path('produit/<int:pk>/evaluer/', views.evaluer_produit, name='evaluer_produit'),
    path('produit/<int:pk>/negocier/', views.proposer_prix, name='proposer_prix'),
    path('commande-confirmee/', views.confirmation_commande, name='confirmation_commande'),
    
    # Paiement Commande
    path('payer-commande/<int:pk>/', views.payer_commande, name='payer_commande'),
    path('commande/<int:pk>/payer/orange/', views.payer_commande_orange, name='payer_commande_orange'),
    path('commande/<int:pk>/payer/mobile/', views.payer_commande_mobile, name='payer_commande_mobile'),
    path('commande/<int:pk>/payer/livraison/', views.payer_commande_livraison, name='payer_commande_livraison'),
    path('commande-paiement-confirme/', views.confirmation_paiement_commande, name='confirmation_paiement_commande'),
    
    # Signaler
    path('signaler/<int:vendeur_pk>/', views.signaler_vendeur, name='signaler_vendeur'),
    
    # Upload
    path('upload-photo-vendeur/', views.upload_photo_vendeur, name='upload_photo_vendeur'),
    path('upload-photo-client/', views.upload_photo_client, name='upload_photo_client'),
    
# Favoris
    path('favori/<int:produit_pk>/toggle/', views.toggle_favori, name='toggle_favori'),
    path('favori/<int:produit_pk>/status/', views.get_favori_status, name='get_favori_status'),
    path('mes-favoris/', views.mes_favoris, name='mes_favoris'),
    
# Notifications
    path('mes-notifications/', views.mes_notifications, name='mes_notifications'),
    
    # API Notifications Polling
    path('api/notifications/nouvelles/', views.api_notifications_nouvelles, name='api_notifications_nouvelles'),
    
    # Messages & Négociations
    path('mes-messages/', views.mes_messages_client, name='mes_messages_client'),
    path('negociation/<int:pk>/chat/', views.chat_negociation, name='chat_negociation'),
    path('negociation/<int:pk>/effacer/', views.effacer_discussion, name='effacer_discussion'),
    path('negociation/<int:pk>/repondre/', views.repondre_negociation, name='repondre_negociation'),
    path('envoyer-message/', views.envoyer_message, name='envoyer_message'),
    
    # Factures
    path('commande/<int:pk>/facture/', views.telecharger_facture, name='telecharger_facture'),
    path('mes-factures/', views.mes_factures, name='mes_factures'),
    
    # Historique
    path('supprimer-historique/', views.supprimer_historique_commandes, name='supprimer_historique'),
    
    # Panier
    path('panier/', views.voir_panier, name='voir_panier'),
    path('panier/ajouter/<int:produit_pk>/', views.ajouter_au_panier, name='ajouter_au_panier'),
    path('panier/supprimer/<int:item_pk>/', views.supprimer_du_panier, name='supprimer_du_panier'),
    path('panier/modifier/<int:item_pk>/', views.modifier_quantite_panier, name='modifier_quantite_panier'),
    path('panier/commander/', views.commander_panier, name='commander_panier'),
    path('panier/payer/<int:paiement_pk>/', views.payer_panier, name='payer_panier'),
    path('panier/confirmation/<int:paiement_pk>/', views.confirmation_panier_paye, name='confirmation_panier_paye'),
    path('api/panier/count/', views.get_panier_count, name='get_panier_count'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
