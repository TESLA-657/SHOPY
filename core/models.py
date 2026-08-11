from django.contrib.auth.hashers import make_password
from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

VILLES_GUINEE= [
     ('Conakry','Conakry'),
     ('Boké','Boké'),
     ('Kindia','Kindia'),
     ('Boké','Boké'),
     ('Mamou','Mamou'),
     ('Labé','Labé'),
     ('Faranah','Faranah'),
     ('Kankan','Kankan'),
     ('Nzérékoré','Nzérékoré'),
     ('Kamsar','Kamsar'),
     ('Siguiri','Siguiri'),
]

# ===== STATUTS =====

STATUT_CLIENT = [
    ('actif', 'Actif'),
    ('non_actif', 'Non actif'),
]

STATUT_VENDEUR = [
    ('en_attente', 'En attente'),
    ('non_actif', 'Non actif'),
    ('actif', 'Actif'),
    ('expire', 'Expiré'),
    ('suspendu', 'Suspendu'),
]

STATUT_COMMANDE = [
    ('en_attente', 'En attente'),
    ('acceptee', 'Acceptée'),
    ('refusee', 'Refusée'),
    ('livree', 'Livrée'),
]

STATUT_ABONNEMENT = [
    ('actif', 'Actif'),
    ('expire', 'Expiré'),
]

# Import des validators de sécurité
from .validators import validate_secure_image, SecureImageValidator
from .audit import AuditLog

# Client
class Client(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    nom = models.CharField(max_length=100)
    numero = models.CharField(max_length=20)
    ville = models.CharField(max_length=100)
    photo = models.ImageField(
        upload_to='clients/', 
        blank=True, 
        null=True,
        validators=[validate_secure_image]  # Validation sécurisée
    )
    date_inscription = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nom
    
# Catégories
class Categorie(models.Model):
    nom = models.CharField(max_length=50)
    icone = models.CharField(max_length=10, default='📦')
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.nom


# Device Token pour Push Notifications (FCM)
class DeviceToken(models.Model):
    """Stocke les tokens FCM des appareils pour les notifications push."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='device_tokens')
    fcm_token = models.TextField()  # Token Firebase Cloud Messaging
    device_type = models.CharField(max_length=20, choices=[
        ('android', 'Android'),
        ('ios', 'iOS'),
        ('web', 'Web'),
    ], default='android')
    date_creation = models.DateTimeField(auto_now_add=True)
    est_actif = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user} - {self.device_type}"



# Favoris
class Favori(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='favoris')
    produit = models.ForeignKey('Produit', on_delete=models.CASCADE)
    date_ajout = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('client', 'produit')
    
class Vendeur(models.Model):
    user=models.OneToOneField(User,on_delete=models.CASCADE, null=True,blank=True)
    nom_boutique = models.CharField(max_length=100)
    numero = models.CharField(max_length=20, unique=True)
    ville = models.CharField(max_length=50,default='Conakry')
    statut = models.CharField(max_length=20, choices=STATUT_VENDEUR, default='non_actif')
    date_inscription = models.DateTimeField(auto_now_add=True)
    verifie = models.BooleanField(default=False)
    raison_suspension = models.TextField(blank=True, default='')
    photo = models.ImageField(
        upload_to='vendeurs/', 
        blank=True, 
        null=True,
        validators=[validate_secure_image]  # Validation sécurisée
    )
    ventes_du_mois = models.IntegerField(default=0)
    dernier_reset_ventes = models.DateField(null=True, blank=True)
    total_produits_crees = models.IntegerField(default=0)
    
# === CHAMPS VENDEUR CERTIFIÉ (Fonctionnalité 6) ===
    est_certifie = models.BooleanField(default=False)
    date_certification = models.DateTimeField(null=True, blank=True)
    note_confiance = models.FloatField(default=0.0)  # Note moyenne 0-5
    nb_evaluations = models.IntegerField(default=0)
    demande_certification = models.BooleanField(default=False)
    date_demande_certification = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        badge = " ✅" if self.est_certifie else ""
        return f"{self.nom_boutique}{badge}"

class FideliteClientVendeur(models.Model):
    vendeur = models.ForeignKey('Vendeur', on_delete=models.CASCADE, related_name='client_fidelites')
    client = models.ForeignKey('Client', on_delete=models.CASCADE, related_name='vendeur_fidelites')
    commandes_count = models.IntegerField(default=0)
    depenses_total = models.IntegerField(default=0)
    reduction_pct = models.IntegerField(default=0)
    dernier_achat = models.DateTimeField(null=True, blank=True)
    validite_jusqua = models.DateField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('vendeur', 'client')
        ordering = ['-commandes_count', '-dernier_achat']

    def __str__(self):
        return f"{self.client.nom} fidèle chez {self.vendeur.nom_boutique}"

    def is_active(self):
        if not self.validite_jusqua:
            return False
        return self.validite_jusqua >= timezone.now().date()

    def niveau(self):
        if self.commandes_count >= 10:
            return 'Or'
        if self.commandes_count >= 6:
            return 'Argent'
        if self.commandes_count >= 3:
            return 'Bronze'
        return 'Débutant'

class Produit(models.Model):
        vendeur = models.ForeignKey('Vendeur', on_delete=models.CASCADE)
        nom = models.CharField(max_length=100)
        photo = models.ImageField(
            upload_to='produits/',
            validators=[validate_secure_image]  # Validation sécurisée
        )
        prix = models.DecimalField(max_digits=10, decimal_places=2)
        quantite = models.PositiveIntegerField()
        description = models.TextField()
        visible = models.BooleanField(default=True)
        categorie = models.ForeignKey(
        Categorie, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='produits')
        
        # Marque du produit (pour les alertes de prix et la recherche)
        marque = models.CharField(max_length=100, blank=True, default='')

        promo = models.BooleanField(default=False)
        prix_promo = models.IntegerField(null=True, blank=True)
        jours_promo= models.IntegerField(null=True, blank=True)
        date_debut_promo=models.DateTimeField(null=True, blank=True)
        date_fin_promo=models.DateTimeField(null=True, blank=True)

        def reduction_pourcentage(self):
            if not self.promo or self.prix_promo is None:
                return 0
            try:
                prix_normal = float(self.prix or 0)
                prix_promo_val = float(self.prix_promo or 0)
            except (TypeError, ValueError):
                return 0
            if prix_normal <= 0 or prix_promo_val >= prix_normal:
                return 0
            return int(round((prix_normal - prix_promo_val) / prix_normal * 100))

        def __str__(self):
            return self.nom
class Commande(models.Model):
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('acceptee', 'Acceptée'),
        ('refusee', 'Refusée'),
        ('annulee', 'Annulée'),
    ]
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE)
    vendeur = models.ForeignKey(Vendeur, on_delete=models.CASCADE)
    nom_client = models.CharField(max_length=100)
    numero_client = models.CharField(max_length=20)
    ville_client = models.CharField(max_length=100)
    message = models.TextField(blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    date_commande = models.DateTimeField(auto_now_add=True)
    quantite= models.PositiveIntegerField(default=1)
    prix_unitaire = models.IntegerField(default=0)
    prix_total = models.IntegerField(default=0)
    archivee = models.BooleanField(default=False)

    # si cette commande a été créée à partir d'un panier payé
    paiement_panier = models.ForeignKey('PaiementPanier', on_delete=models.SET_NULL, null=True, blank=True, related_name='commandes')

    def __str__(self):
        return f"Commande {self.pk} - {self.produit.nom}"


# Message de Négociation entre le vendeur et le client


class MessageNegociation(models.Model):
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE, related_name='negociations')
    client_nom = models.CharField(max_length=100)
    client_numero = models.CharField(max_length=20)
    vendeur = models.ForeignKey(Vendeur, on_delete=models.CASCADE)
    prix_propose = models.IntegerField()
    message = models.TextField(blank=True)
    reponse_vendeur = models.TextField(blank=True)
    statut = models.CharField(max_length=20, choices=[
        ('en_attente', 'En attente'),
        ('accepte', 'Accepté'),
        ('refuse', 'Refusé'),
        ('contre_offre', 'Contre-offre'),
], default='en_attente')
    date = models.DateTimeField(auto_now_add=True)
    
    # Champs pour suivre les messages non lus (False = non lu, True = lu)
    vendor_lu = models.BooleanField(default=False)
    client_lu = models.BooleanField(default=False)


class ChatMessage(models.Model):
    NEG_STATES_SENDER = [
        ('vendeur', 'Vendeur'),
        ('client', 'Client'),
    ]

    negociation = models.ForeignKey(
        MessageNegociation,
        on_delete=models.CASCADE,
        related_name='chats',
    )
    sender_type = models.CharField(max_length=10, choices=NEG_STATES_SENDER, default='client')
    content = models.TextField(blank=True)
    prix_propose = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"ChatMessage({self.negociation_id}) from {self.sender_type}" 


# Notification in-app
class Notification(models.Model):
    TYPE_CHOICES = [
        ('commande', 'Commande'),
        ('abonnement', 'Abonnement'),
        ('message', 'Message'),
        ('securite', 'Sécurité'),
        ('systeme', 'Système'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='systeme')
    titre = models.CharField(max_length=100)
    message = models.TextField()
    lue = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)
    lien = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.user} — {self.titre}"

# Évaluation produit
class Evaluation(models.Model):
    produit = models.ForeignKey('Produit', on_delete=models.CASCADE, related_name='evaluations')
    client_nom = models.CharField(max_length=100)
    client_numero = models.CharField(max_length=20)
    note = models.IntegerField(default=5)  # 1 à 5
    commentaire = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.produit.nom} — {self.note}/5"

# Suivi commande
class SuiviCommande(models.Model):
    ETAPE_CHOICES = [
        ('commandee', 'Commandée'),
        ('payee', 'Payée'),
        ('acceptee', 'Acceptée par le vendeur'),
        ('en_livraison', 'En cours de livraison'),
        ('livree', 'Livrée'),
        ('annulee', 'Annulée'),
    ]
    commande = models.ForeignKey('Commande', on_delete=models.CASCADE, related_name='suivis')
    etape = models.CharField(max_length=20, choices=ETAPE_CHOICES)
    date = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"Commande #{self.commande.pk} — {self.etape}"
        
class Administrateur(models.Model):
        nom = models.CharField(max_length=100)
        email = models.EmailField(unique=True)
        mot_de_passe = models.CharField(max_length=255)
        def save(self,*args,**kwargs):
            if not self.mot_de_passe.startswith('pbkdf2_sha256$'):
                self.mot_de_passe=make_password(self.mot_de_passe)
            super().save(*args,**kwargs)


        def __str__(self):
            return self.nom
        
class PlanAbonnement(models.Model):
    NOM_CHOICES = [
        ('gratuit', 'Gratuit'),
        ('essentiel', 'Essentiel'),
        ('pro', 'Pro'),
        ('business', 'Business'),
    ]
    nom = models.CharField(max_length=20, choices=NOM_CHOICES, unique=True)
    prix = models.IntegerField(default=0)
    limite_produits = models.IntegerField(default=5)  # -1 = illimité
    duree_jours = models.IntegerField(default=30)

    def __str__(self):
        return self.nom

class Abonnement(models.Model):
    STATUT_CHOICES = [
        ('essai', 'Essai gratuit'),
        ('actif', 'Actif'),
        ('suspendu', 'Suspendu'),
        ('expire', 'Expiré'),
    ]
    vendeur = models.OneToOneField(Vendeur, on_delete=models.CASCADE, related_name='abonnement')
    plan = models.ForeignKey(PlanAbonnement, on_delete=models.SET_NULL, null=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='essai')
    date_debut = models.DateTimeField(auto_now_add=True)
    date_fin = models.DateTimeField(null=True, blank=True)
    rappel_envoye = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.vendeur.nom_boutique} - {self.plan}"

    def jours_restants(self):
        if self.date_fin:
            delta = self.date_fin - timezone.now()
            total_secondes = int(delta.total_seconds())
            if total_secondes <= 0:
                return 0
            return max(0, delta.days)
        return 0
    def temps_restant_precis(self):
        if self.date_fin:
            delta = self.date_fin - timezone.now()
            total_secondes = int(delta.total_seconds())
            if total_secondes <= 0:
                return "Expiré"
            
            jours = delta.days
            heures = (total_secondes % 86400) // 3600
            minutes = (total_secondes % 3600) // 60
            secondes = total_secondes % 60
            
            if jours > 1:
                return f"{jours} jours restants"
            elif jours == 1:
                return f"1 jour {heures}h restants"
            elif heures > 0:
                return f"{heures}h {minutes}min restantes"
            elif minutes > 0:
                return f"{minutes}min {secondes}s restantes"
            else:
                return f"{secondes} secondes restantes"
        return "—"

    def moins_de_24h(self):
        if self.date_fin:
            delta = self.date_fin - timezone.now()
            return 0 < delta.total_seconds() < 86400
        return False

    def est_expire(self):
        if self.date_fin:
            return timezone.now() > self.date_fin
        return False

class PaiementAbonnement(models.Model):
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('valide', 'Validé'),
        ('refuse', 'Refusé'),
    ]
    vendeur = models.ForeignKey(Vendeur, on_delete=models.CASCADE, related_name='paiements')
    plan = models.ForeignKey(PlanAbonnement, on_delete=models.CASCADE)
    numero_paiement = models.CharField(max_length=20)
    montant = models.IntegerField()
    reference = models.CharField(max_length=100, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    date_soumission = models.DateTimeField(auto_now_add=True)
    date_validation = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.vendeur.nom_boutique} - {self.plan.nom} - {self.statut}"


class Signalement(models.Model):
    RAISON_CHOICES = [
        ('arnaque', 'Arnaque'),
        ('produit_non_conforme', 'Produit non conforme'),
        ('mauvais_service', 'Mauvais service'),
        ('autre', 'Autre'),
    ]
    client_nom = models.CharField(max_length=100)
    client_numero = models.CharField(max_length=20)
    vendeur = models.ForeignKey(Vendeur, on_delete=models.CASCADE, related_name='signalements')
    raison = models.CharField(max_length=30, choices=RAISON_CHOICES)
    description = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)
    traite = models.BooleanField(default=False)

    def __str__(self):
        return f"Signalement contre {self.vendeur.nom_boutique}"
    

    
# @receiver(post_save, sender=Commande)
# def mettre_a_jour_stock(sender, instance, created, **kwargs):
#     # Stock is now reduced when payment is confirmed, not when order is created
#     # This allows the client to complete payment before stock is deducted
#     pass

class PaiementCommande(models.Model):
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('valide', 'Validé'),
        ('refuse', 'Refusé'),
    ]
    MODE_PAIEMENT_CHOICES = [
        ('orange_money', 'Orange Money'),
        ('carte_bancaire', 'Carte Bancaire'),
        ('paiement_livraison', 'Paiement à la livraison'),
        ('virement_bancaire', 'Virement bancaire'),
    ]

    commande = models.OneToOneField(Commande, on_delete=models.CASCADE, related_name='paiement')
    # optionnel: rattacher le paiement de commande au paiement panier unique
    paiement_panier = models.ForeignKey('PaiementPanier', on_delete=models.SET_NULL, null=True, blank=True, related_name='paiements_commandes')

    mode_paiement = models.CharField(
        max_length=30,
        choices=MODE_PAIEMENT_CHOICES,
        default='orange_money'
    )
    numero_paiement = models.CharField(max_length=20)
    montant = models.IntegerField()
    reference = models.CharField(max_length=100, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    date_soumission = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Paiement commande #{self.commande.pk}"


class Panier(models.Model):
    client = models.OneToOneField(Client, on_delete=models.CASCADE, related_name='panier')
    date_modification = models.DateTimeField(auto_now=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Panier de {self.client.nom}"


class PanierItem(models.Model):
    panier = models.ForeignKey(Panier, on_delete=models.CASCADE, related_name='items')
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE)
    quantite = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('panier', 'produit')

    def __str__(self):
        return f"{self.produit.nom} x{self.quantite}"


class PaiementPanier(models.Model):
    STATUT_CHOICES = [
        ('en_attente', 'En attente'),
        ('valide', 'Validé'),
        ('refuse', 'Refusé'),
    ]

    MODE_PAIEMENT_CHOICES = [
        ('orange_money', 'Orange Money'),
        ('mobile_money', 'Mobile Money'),
        ('carte_bancaire', 'Carte Bancaire'),
        ('paiement_livraison', 'Paiement à la livraison'),
        ('virement_bancaire', 'Virement bancaire'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='paiements_panier')
    montant_total = models.IntegerField(default=0)
    mode_paiement = models.CharField(
        max_length=30,
        choices=MODE_PAIEMENT_CHOICES,
        default='orange_money'
    )
    numero_paiement = models.CharField(max_length=20)
    reference = models.CharField(max_length=100, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='en_attente')
    date_soumission = models.DateTimeField(auto_now_add=True)
    date_validation = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Paiement panier #{self.pk} — {self.client.nom}"


# ============================================================
# NOUVEAUX MODÈLES
# ============================================================

# --- MODÈLE GARANTIE ACHETEUR (Fonctionnalité 5) ---
class GarantieAcheteur(models.Model):
    STATUT_CHOICES = [
        ('active', 'Active'),
        ('utilisee', 'Utilisée'),
        ('expiree', 'Expirée'),
        ('refusee', 'Refusée'),
    ]
    commande = models.ForeignKey(Commande, on_delete=models.CASCADE, related_name='garantie')
    client_numero = models.CharField(max_length=20)  # номер телефона клиента
    montant_original = models.IntegerField()  #Montant total de la commande
    montant_rembourse = models.IntegerField(default=0)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='active')
    date_activation = models.DateTimeField(auto_now_add=True)
    date_expiration = models.DateTimeField()  # 30 jours après activation
    motif_refus = models.TextField(blank=True, default='')
    
    def __str__(self):
        return f"Garantie #{self.pk} - Commande {self.commande.pk}"
    
    def est_active(self):
        from django.utils import timezone
        return self.statut == 'active' and timezone.now() < self.date_expiration
    
    def jours_restants(self):
        from django.utils import timezone
        if self.statut != 'active':
            return 0
        delta = self.date_expiration - timezone.now()
        return max(0, delta.days)


# --- MODÈLE FLASH SALE (Fonctionnalité 7) ---
class FlashSale(models.Model):
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE, related_name='flash_sales')
    prix_flash = models.IntegerField()  # Prix réduit
    quantite_disponible = models.PositiveIntegerField(default=1)
    quantite_vendue = models.PositiveIntegerField(default=0)
    date_debut = models.DateTimeField(auto_now_add=True)
    date_fin = models.DateTimeField()  # Durée: 1-24 heures
    est_active = models.BooleanField(default=True)
    cree_par = models.ForeignKey(Vendeur, on_delete=models.CASCADE)
    
    def __str__(self):
        return f"FlashSale: {self.produit.nom} - {self.prix_flash} GNF"
    
    def est_en_cours(self):
        from django.utils import timezone
        maintenant = timezone.now()
        return (self.est_active and 
                maintenant >= self.date_debut and 
                maintenant <= self.date_fin)
    
    def stock_restant(self):
        return max(0, self.quantite_disponible - self.quantite_vendue)
    
    def reduction_pourcentage(self):
        """Calcule le pourcentage de réduction"""
        prix_normal = int(self.produit.prix)
        if prix_normal > 0:
            reduction = ((prix_normal - self.prix_flash) / prix_normal) * 100
            return int(reduction)
        return 0
    
    def temps_restant(self):
        from django.utils import timezone
        if not self.est_en_cours():
            return "Terminé"
        delta = self.date_fin - timezone.now()
        if delta.total_seconds() <= 0:
            return "Terminé"
        heures = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        if delta.days > 0:
            return f"{delta.days}j {heures}h"
        elif heures > 0:
            return f"{heures}h {minutes}min"
        else:
            return f"{minutes}min"


# --- MODÈLE ALERTE PRIX (Fonctionnalité 4 - Assistant IA) ---
class AlertePrix(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='alertes_prix')
    produit_nom = models.CharField(max_length=100)  # Nom du produit recherché
    marque = models.CharField(max_length=50, blank=True)
    prix_cible = models.IntegerField()  # Prix cible souhaité
    ville = models.CharField(max_length=50, blank=True)
    notifie = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)
    produit_correspondant = models.ForeignKey(Produit, on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        return f"Alerte: {self.produit_nom} < {self.prix_cible} GNF"


# --- MODÈLE ÉVALUATION VENDEUR (Fonctionnalité 6) ---
class EvaluationVendeur(models.Model):
    vendeur = models.ForeignKey(Vendeur, on_delete=models.CASCADE, related_name='evaluations')
    client_nom = models.CharField(max_length=100)
    client_numero = models.CharField(max_length=20)
    note = models.IntegerField(default=5)  # 1 à 5
    commentaire = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Évaluation {self.vendeur.nom_boutique} - {self.note}/5"


# Create your models here.


