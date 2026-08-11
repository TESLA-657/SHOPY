from django.contrib import admin
from .models import Client, Vendeur, Abonnement, Produit, Commande, Notification, Administrateur, PaiementAbonnement, Signalement, Categorie, Evaluation, PaiementCommande, AuditLog
from django.core.mail import send_mail

def save(self, *args, **kwargs):
    # On vérifie si le statut passe à 'ACTIF'
    if self.pk: # Si le vendeur existe déjà
        ancien_vendeur = Vendeur.objects.get(pk=self.pk)
        if ancien_vendeur.statut != 'actif' and self.statut == 'actif':
            # Envoyer l'email
            send_mail(
                'Votre boutique SHOPY est active !',
                f'Bonjour {self.nom_boutique}, votre compte a été approuvé par l\'administrateur.',
                'admin@shopy.com',
                [self.user.email],
                fail_silently=False,)
    super().save(*args, **kwargs)
# Configuration pour voir les détails dans les listes

@admin.register(Abonnement)
class AbonnementAdmin(admin.ModelAdmin):
    list_display = ['vendeur', 'plan', 'statut', 'date_fin']

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        vendeur = obj.vendeur
        if obj.statut == 'actif':
            vendeur.statut = 'actif'
            vendeur.raison_suspension = ''
            vendeur.save()
            vendeur.produit_set.update(visible=True)
        elif obj.statut == 'suspendu':
            vendeur.statut = 'suspendu'
            vendeur.raison_suspension = 'Abonnement expiré.'
            vendeur.save()
            vendeur.produit_set.update(visible=False)

@admin.register(Vendeur)
class VendeurAdmin(admin.ModelAdmin):
    list_display = ['nom_boutique', 'ville', 'statut', 'verifie', 'numero']
    list_filter = ['statut', 'verifie']
    actions = ['activer_vendeurs', 'suspendre_vendeurs', 'verifier_vendeurs']
    
    def activer_vendeurs(self, request, queryset):
        from django.utils import timezone
        from datetime import timedelta
        for vendeur in queryset:
            vendeur.statut = 'actif'
            vendeur.raison_suspension = ''
            vendeur.save()
            # ← Rendre les produits visibles
            vendeur.produit_set.update(visible=True)
            try:
                abo = vendeur.abonnement
                if abo.statut == 'suspendu':
                    abo.statut = 'actif'
                    abo.date_fin = timezone.now() + timedelta(days=30)
                    abo.save()
            except:
                pass
        self.message_user(request, f"{queryset.count()} vendeur(s) activé(s).")
    activer_vendeurs.short_description = "✅ Activer les vendeurs sélectionnés"
    
    def suspendre_vendeurs(self, request, queryset):
        for vendeur in queryset:
            vendeur.statut = 'suspendu'
            vendeur.save()
            vendeur.produit_set.update(visible=False)
    suspendre_vendeurs.short_description = "🔒 Suspendre les vendeurs sélectionnés"

    def verifier_vendeurs(self, request, queryset):
        queryset.update(verifie=True)
    verifier_vendeurs.short_description = "✅ Marquer comme vérifié"

@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ['icone', 'nom', 'slug']
    prepopulated_fields = {'slug': ('nom',)}

@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    list_display = ['nom', 'vendeur', 'prix', 'quantite', 'categorie', 'visible', 'promo']
    list_filter = ['visible', 'promo', 'categorie']

@admin.register(Commande)
class CommandeAdmin(admin.ModelAdmin):
    list_display = ['pk', 'produit', 'nom_client', 'vendeur', 'statut', 'date_commande']
    list_filter = ['statut']

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['nom', 'numero', 'ville']

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'type', 'titre', 'lue', 'date']
    list_filter = ['type', 'lue']

@admin.register(Signalement)
class SignalementAdmin(admin.ModelAdmin):
    list_display = ['vendeur', 'client_nom', 'raison', 'traite', 'date']
    list_filter = ['raison', 'traite']

@admin.register(PaiementAbonnement)
class PaiementAbonnementAdmin(admin.ModelAdmin):
    list_display = ['vendeur', 'plan', 'montant', 'statut', 'date_soumission']
    list_filter = ['statut']

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'user', 'action', 'details', 'ip_address']
    list_filter = ['action']
    search_fields = ['details', 'user__username', 'ip_address']
    ordering = ['-timestamp']

admin.site.register(Evaluation)
admin.site.register(PaiementCommande)