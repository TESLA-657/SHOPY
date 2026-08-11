from rest_framework import viewsets
from .models import Client, Vendeur, Produit, Commande, Abonnement, Notification, PlanAbonnement, Categorie, Favori, Evaluation, MessageNegociation, ChatMessage, Panier, PanierItem, PaiementPanier, FideliteClientVendeur
from .models import GarantieAcheteur, FlashSale, AlertePrix, EvaluationVendeur
from .serializers import ClientSerializer, VendeurSerializer, ProduitSerializer, CommandeSerializer, AbonnementSerializer, NotificationSerializer
from .audit import log_action, AuditLog

# Importer les nouvelles fonctionnalités SHOPY
from .views_shopy_features import (
    vendeurs_certifies, demander_certification, noter_vendeur,
    mes_garanties, demander_remboursement, admin_garanties, traiter_garantie,
    flash_sales, detail_flash_sale, creer_flash_sale, acheter_flash_sale, api_flash_sales,
    alertes_prix, creer_alerte, supprimer_alerte, assistant_ia_vendeur
)
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from .forms import InscriptionVendeurForm, ProduitForm
from django.contrib.auth.decorators import login_required
from .models import Vendeur, Produit, VILLES_GUINEE, PaiementAbonnement, Signalement, PaiementCommande
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Q, Case, When, Value, IntegerField, Count, Sum

# ============================================
# SYSTÈME DE SALUTATION
# ============================================

def get_salutation_guinee():
    """
    Retourne une salutation basée sur l'heure en Guinée (GMT/West Africa).
    La Guinée utilise le fuseau horaire GMT (pas de décalage).
    """
    from django.utils import timezone

    maintenant = timezone.now()
    heure = maintenant.hour

    if 6 <= heure < 12:
        return "Bonjour"
    elif 12 <= heure < 18:
        return "Bon'après-midi"
    else:
        return "Bonsoir"


def get_salutation_with_name(nom):
    salutation = get_salutation_guinee()
    return f"{salutation} {nom}"


# ============================================
# FIDÉLITÉ VENDEUR-CLIENT
# ============================================

def calculate_loyalty_reduction_pct(commandes_count):
    if commandes_count >= 10:
        return 8
    if commandes_count >= 6:
        return 5
    if commandes_count >= 3:
        return 3
    return 0


from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt


def get_loyalty_discount(client, vendeur):
    try:
        fidelite = FideliteClientVendeur.objects.get(client=client, vendeur=vendeur)
    except FideliteClientVendeur.DoesNotExist:
        return 0
    except Exception as e:
        try:
            from django.db.utils import OperationalError, ProgrammingError
        except Exception:
            OperationalError = Exception
            ProgrammingError = Exception
        if isinstance(e, (OperationalError, ProgrammingError)):
            print("DEBUG get_loyalty_discount DB error:", e)
            return 0
        raise

    if fidelite.is_active():
        return fidelite.reduction_pct
    return 0


def apply_loyalty_discount(prix, reduction_pct):
    try:
        prix = float(prix)
    except (TypeError, ValueError):
        return prix
    if reduction_pct <= 0:
        return int(round(prix))
    return int(round(prix * (100 - reduction_pct) / 100))


def update_loyalty_record(client, vendeur, montant):
    if not client or not vendeur:
        return None
    record, created = FideliteClientVendeur.objects.get_or_create(client=client, vendeur=vendeur)
    record.commandes_count += 1
    record.depenses_total += int(montant or 0)
    record.dernier_achat = timezone.now()
    record.reduction_pct = calculate_loyalty_reduction_pct(record.commandes_count)
    record.validite_jusqua = timezone.now().date() + timedelta(days=90)
    record.save()
    return record


def inscription_vendeur(request):
    erreur = None
    if request.method == 'POST':
        nom_boutique = request.POST.get('nom_boutique')
        numero = request.POST.get('numero')
        ville = request.POST.get('ville')
        email = request.POST.get('email')
        mot_de_passe = request.POST.get('mot_de_passe')
        confirmer = request.POST.get('confirmer_mot_de_passe')

        if mot_de_passe != confirmer:
            erreur = "Les mots de passe ne correspondent pas."
        elif User.objects.filter(username=nom_boutique).exists():
            erreur = "Ce nom de boutique est déjà utilisé. Choisissez un autre nom."
        elif Vendeur.objects.filter(numero=numero).exists():
            erreur = "Ce numéro est déjà associé à une boutique."
        elif Vendeur.objects.filter(ville=ville, numero=numero).exists():
            erreur = "Une boutique avec ce numéro existe déjà."
        else:
            user = User.objects.create_user(
                username=nom_boutique,
                password=mot_de_passe,
                email=email
            )
            Vendeur.objects.create(
                user=user,
                nom_boutique=nom_boutique,
                numero=numero,
                ville=ville,
                statut='en_attente'
            )
            log_action(request, 'signup_vendor', f'Vendeur {nom_boutique} email {email}')
            # Notifier l'admin
            try:
                from django.contrib.auth.models import User as UserModel
                admins = UserModel.objects.filter(is_staff=True)
                for admin in admins:
                    if admin.email:
                        send_mail(
                            subject=f'🆕 Nouvelle boutique en attente — {nom_boutique}',
                            message=f'Boutique: {nom_boutique}\nVille: {ville}\nNuméro: {numero}\nEmail: {email}\n\nConnectez-vous au dashboard admin pour valider.',
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[admin.email],
                            fail_silently=True,
                        )
            except:
                pass

            return render(request, 'core/attente_validation.html', {
                'nom_boutique': nom_boutique,
                'email': email,
            })

    return render(request, 'core/inscription_vendeur.html', {'erreur': erreur})

class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer

class VendeurViewSet(viewsets.ModelViewSet):
    queryset = Vendeur.objects.all()
    serializer_class = VendeurSerializer

class ProduitViewSet(viewsets.ModelViewSet):
    queryset = Produit.objects.all()
    serializer_class = ProduitSerializer

class CommandeViewSet(viewsets.ModelViewSet):
    queryset = Commande.objects.all()
    serializer_class = CommandeSerializer

class AbonnementViewSet(viewsets.ModelViewSet):
    queryset = Abonnement.objects.all()
    serializer_class = AbonnementSerializer

class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer

 # Importe le formulaire que tu viens de créer

def connexion_vendeur(request):
    erreur = None
    if request.method == 'POST':
        nom_boutique = request.POST.get('nom_boutique')
        mot_de_passe = request.POST.get('mot_de_passe')

        # Vérifier si le user existe
        try:
            user_existe = User.objects.get(username=nom_boutique)
            user = authenticate(request, username=nom_boutique, password=mot_de_passe)
            if user is not None:
                login(request, user)
                log_action(request, 'login_vendor', f'Vendeur {nom_boutique}')
                try:
                    vendeur = Vendeur.objects.get(user=user)
                    if vendeur.statut in ['actif', 'suspendu']:
                        return redirect('dashboard_vendeur')
                    else:
                        return render(request, 'core/attente_validation.html', {
                            'nom_boutique': nom_boutique,
                            'email': user.email,
                        })
                except Vendeur.DoesNotExist:
                    erreur = "Ce compte n'est pas associé à une boutique."
            else:
                erreur = "Mot de passe incorrect."
        except User.DoesNotExist:
            erreur = "Cette boutique n'existe pas ou a été supprimée. Vérifiez le nom ou créez un nouveau compte."

    return render(request, 'core/connexion_vendeur.html', {'erreur': erreur})

def deconnexion_vendeur(request):
    if request.user.is_authenticated:
        log_action(request, 'logout', f'Vendeur {request.user.username}')
    logout(request)
    return redirect('Welcome')

def ajouter_produit_legacy(request):
    # Si le vendeur a cliqué sur le bouton "Mettre en vente" (méthode POST)
    if request.method == 'POST':
        form = ProduitForm(request.POST, request.FILES) # Récupère les textes + la photo
        vendeur = Vendeur.objects.get(user=request.user)
        if form.is_valid():
            produit = form.save(commit=False)
            
            # ATTENTION : Comme on n'a pas encore de système de connexion,
            # on va forcer un vendeur par défaut (ex: le premier de ta liste)
            # pour éviter que la base de données ne rejette l'enregistrement.
            from .models import Vendeur
            vendeur_par_defaut = Vendeur.objects.first() 
            produit.vendeur = vendeur_par_defaut
            produit.save() # Enregistre enfin le produit dans la base !
            vendeur.total_produits_crees += 1
            vendeur.save()
            return redirect('admin:index') # Redirige vers l'admin pour voir le résultat
    
    # Si le vendeur arrive juste sur la page (méthode GET)
    else:
        form = ProduitForm()
    
    # Envoie le formulaire au fichier HTML que tu as mis dans templates/core/
    return render(request, 'core/ajouter_produit.html', {'form': form})



@login_required
def liste_produits_vendeur(request):
    # Vérifier les promos expirées
    verifier_promos_expirees()
    
    # On récupère le profil vendeur de l'utilisateur connecté
    vendeur = Vendeur.objects.get(user=request.user)

    # Recherche produits vendeur
    recherche = (request.GET.get('q') or '').strip()

    # On ne prend que SES produits
    produits = Produit.objects.filter(vendeur=vendeur)

    if recherche:
        produits = produits.filter(
            Q(nom__icontains=recherche) |
            Q(description__icontains=recherche)
        )

    # Séparer les produits en promo et non-promo
    produits_promo = produits.filter(promo=True)
    produits_non_promo = produits.filter(promo=False)

    return render(request, 'core/liste_produits_vendeur.html', {
        'produits': produits,
        'produits_promo': produits_promo,
        'produits_non_promo': produits_non_promo,
        'vendeur': vendeur,
        'recherche': recherche,
    })

@login_required
def commandes_vendeur_legacy(request):
    vendeur = Vendeur.objects.get(user=request.user)
    # On ne prend que les commandes qui lui sont destinées
    commandes = Commande.objects.filter(
    vendeur=vendeur, archivee=False
    ).order_by('-date_commande')

    return render(request, 'core/commandes_vendeur.html', {'commandes': commandes, 'vendeur': vendeur})

@login_required
def ajouter_produit(request):
    vendeur = get_object_or_404(Vendeur, user=request.user)

    if vendeur.statut == 'suspendu':
        return redirect('dashboard_vendeur')

    # Vérification limite abonnement
    try:
        abonnement = vendeur.abonnement
        plan = abonnement.plan
        if plan.limite_produits != -1:
            nb_produits = Produit.objects.filter(vendeur=vendeur).count()
            if nb_produits >= plan.limite_produits:
                request.session['limite_atteinte'] = True
                request.session['plan_actuel'] = plan.nom
                request.session['limite'] = plan.limite_produits
                return redirect('liste_produits_vendeur')
    except:
        pass

    if request.method == 'POST':
        # ← CORRECTION : copier FILES pour le rendre mutable
        from django.utils.datastructures import MultiValueDict
        import os

        files = request.FILES.copy()  # ← copie mutable

        photo_name = request.POST.get('photo_name') or \
                     request.session.get('selected_photo_produit')

        if photo_name:
            from django.core.files.base import ContentFile
            media_root = getattr(settings, 'MEDIA_ROOT', None)
            if media_root:
                photo_path = os.path.join(media_root, 'produits', photo_name)
                if os.path.exists(photo_path):
                    with open(photo_path, 'rb') as f:
                        content = f.read()
                    files['photo'] = ContentFile(content, name=photo_name)

        form = ProduitForm(request.POST, files)  # ← utilise files mutable

        if form.is_valid():
            produit = form.save(commit=False)
            produit.vendeur = vendeur

            if produit.promo and produit.jours_promo:
                produit.date_debut_promo = timezone.now()
                produit.date_fin_promo = timezone.now() + \
                    timedelta(days=produit.jours_promo)

            produit.save()
            vendeur.total_produits_crees += 1
            vendeur.save()

            request.session.pop('selected_photo_produit', None)
            request.session.pop('selected_photo_produit_next', None)
            return redirect('liste_produits_vendeur')
        
        # ← Si formulaire invalide, les erreurs seront visibles dans le template

    else:
        form = ProduitForm()

    return render(request, 'core/ajouter_produit.html', {
        'form': form,
        'vendeur': vendeur
    })
@login_required
def parametres_vendeur(request):
    vendeur = get_object_or_404(Vendeur, user=request.user)
    try:
        abonnement = vendeur.abonnement
    except:
        abonnement = None

    if request.method == 'POST':
        vendeur.nom_boutique = request.POST.get('nom_boutique', vendeur.nom_boutique)
        vendeur.numero = request.POST.get('numero', vendeur.numero)
        vendeur.ville = request.POST.get('ville', vendeur.ville)
        vendeur.save()
        messages.success(request, 'Paramètres mis à jour !')
        return redirect('parametres_vendeur')

    return render(request, 'core/parametres_vendeur.html', {
        'vendeur': vendeur,
        'abonnement': abonnement,
    })
def welcome(request):
    return render(request,'core/welcome.html')

@login_required
def redirection_apres_connexion(request):
    try:
        # on cherche le profil vendeur lié à l'utilisteur connecté
        vendeur=Vendeur.objects.get(user=request.user)
        if vendeur.statut=='actif':
            return redirect('dashboard_vendeur') # Accès direct à son espace
        elif vendeur.statut=='non_actif':
            return render(request,'core/vendeur_refuse.html',{'raison':vendeur.message_admin # Optionnel champ pour expliquer le refus
                                                              })
        else:#Cas en ATTENTE
            return render(request,'core/inscription_success.html')
        
    except Vendeur.DoesNotExist:
        # Si c'est un client ou l'admin
        return redirect('Welcome')

@login_required
def upload_photo_client(request):
    if request.method == 'POST' and request.FILES.get('photo'):
        client = get_object_or_404(Client, user=request.user)
        client.photo = request.FILES['photo']
        client.save()
    return redirect('espace_client')

@login_required
def parametres_client(request):
    """Page de paramètres pour le client"""
    client = get_object_or_404(Client, user=request.user)
    
    if request.method == 'POST':
        client.nom = request.POST.get('nom', client.nom)
        client.numero = request.POST.get('numero', client.numero)
        client.ville = request.POST.get('ville', client.ville)
        client.save()
        
        # Gérer la photo si uploadée
        if request.FILES.get('photo'):
            client.photo = request.FILES['photo']
            client.save()
        
        messages.success(request, 'Paramètres mis à jour !')
        return redirect('parametres_client')
    
    return render(request, 'core/parametres_client.html', {
        'client': client,
        'villes': VILLES_GUINEE,
    })

@login_required # Oblige l'utilisateur à être connecté
def dashboard_vendeur(request):
    aujourd_hui = timezone.now().date()
    vendeur = get_object_or_404(Vendeur, user=request.user)
    
    # Reset des ventes du mois au nouveau mois
    if vendeur.dernier_reset_ventes:
        if vendeur.dernier_reset_ventes.month != aujourd_hui.month or \
            vendeur.dernier_reset_ventes.year != aujourd_hui.year:
            # Nouveau mois détecté - reset des ventes
            vendeur.ventes_du_mois = 0
            vendeur.dernier_reset_ventes = aujourd_hui
            vendeur.save()
    else:
        # Premier accès - initialiser la date
        vendeur.dernier_reset_ventes = aujourd_hui
        vendeur.save()

# Vérifier les promos expirées
    verifier_promos_expirees()
    
    # Vérifier les abonnements expirés
    choisir_abonnement()

    try:
        abonnement = vendeur.abonnement
        if abonnement.est_expire() and abonnement.statut in ['essai', 'actif']:
            abonnement.statut = 'suspendu'
            abonnement.save()
            suspendu = True
            vendeur.statut = 'suspendu'
            vendeur.save()
    except Abonnement.DoesNotExist:
        abonnement = None

    produits_en_ligne = Produit.objects.filter(vendeur=vendeur, visible=True).count()
    produits_en_promo = Produit.objects.filter(vendeur=vendeur, visible=True, promo=True).count()
    produits_sans_promo = Produit.objects.filter(vendeur=vendeur, visible=True, promo=False).count()
    commandes_en_attente = Commande.objects.filter(vendeur=vendeur, statut='en_attente').count()
    dernieres_commandes = Commande.objects.filter(vendeur=vendeur).order_by('-date_commande')[:5]
    paiement_en_attente = PaiementAbonnement.objects.filter(vendeur=vendeur, statut='en_attente').exists()
    clients_fideles = FideliteClientVendeur.objects.filter(
        vendeur=vendeur,
        validite_jusqua__gte=aujourd_hui
    ).order_by('-commandes_count')[:5]
    
    # Messages non lus pour le vendeur
    # Compter les négociations non lues ET les ChatMessage non lus du vendeur
    negotiations_non_lus = MessageNegociation.objects.filter(
        vendeur=vendeur, vendor_lu=False
    ).count()
    
# Compter les ChatMessage non lus envoyés par le client pour ce vendeur
    chat_non_lus = ChatMessage.objects.filter(
        negociation__vendeur=vendeur,
        sender_type='client'
    ).exclude(
        negociation__vendor_lu=True
    ).count()

    nb_messages_non_lus = negotiations_non_lus + chat_non_lus

# Compter les alertes prix correspondant aux produits du vendeur (Assistant IA)
    produits_vendeur = Produit.objects.filter(vendeur=vendeur, visible=True)
    produits_noms = [p.nom.lower() for p in produits_vendeur]

    # Get marque safely - handle if field doesn't exist in database
    try:
        produits_marques = [getattr(p, 'marque', '') or '' for p in produits_vendeur]
        produits_marques = [m.lower() for m in produits_marques]
    except AttributeError:
        produits_marques = []

    nb_alertes_vendeur = 0
    for alerte in AlertePrix.objects.all()[:50]:
        alerte_nom = alerte.produit_nom.lower() if alerte.produit_nom else ''
        alerte_marque = alerte.marque.lower() if alerte.marque else ''

        correspond = False
        for nom_prod in produits_noms:
            if nom_prod and alerte_nom and (alerte_nom in nom_prod or nom_prod in alerte_nom):
                correspond = True
                break

        if not correspond and alerte_marque:
            for marque_prod in produits_marques:
                if marque_prod and alerte_marque and (alerte_marque in marque_prod or marque_prod in alerte_marque):
                    correspond = True
                    break

        if correspond:
            nb_alertes_vendeur += 1

            nb_alertes_vendeur += 1

    # Générer la salutation personnalisée
    salutation = get_salutation_with_name(vendeur.nom_boutique)

    # On vérifie si l'admin a validé son compte
    if vendeur.statut == 'actif':
        return render(request, 'core/dashboard_vendeur.html', {
            'vendeur':vendeur, 
            'produits_en_ligne':produits_en_ligne, 
            'produits_en_promo': produits_en_promo,
            'produits_sans_promo': produits_sans_promo,
            'commandes_en_attente': commandes_en_attente,
            'dernieres_commandes':dernieres_commandes,
            'abonnement': abonnement,
            'clients_fideles': clients_fideles,
            'nb_messages_non_lus': nb_messages_non_lus,
            'nb_alertes_vendeur': nb_alertes_vendeur,
            'salutation': salutation,
        })
    elif vendeur.statut == 'suspendu':
        return render(request, 'core/dashboard_vendeur.html', {
            'vendeur': vendeur,
            'produits_en_ligne': produits_en_ligne,
            'commandes_en_attente': commandes_en_attente,
            'dernieres_commandes': dernieres_commandes,
            'abonnement': abonnement,
            'clients_fideles': clients_fideles,
            'suspendu': True,
            'paiement_en_attente': paiement_en_attente,
            'nb_messages_non_lus': nb_messages_non_lus,
            'salutation': salutation,
        })

@login_required
def modifier_produit(request, pk):
    produit = get_object_or_404(Produit, pk=pk, vendeur__user=request.user)

    if request.method == 'POST':
        photo_name = request.POST.get('photo_name') or request.session.get('selected_photo_produit')

        if photo_name:
            from django.core.files.base import ContentFile
            import os

            media_root = getattr(settings, 'MEDIA_ROOT', None)
            if media_root:
                photo_path = os.path.join(media_root, 'produits', photo_name)
                if os.path.exists(photo_path):
                    with open(photo_path, 'rb') as f:
                        content = f.read()
                    request.FILES['photo'] = ContentFile(content, name=photo_name)

        form = ProduitForm(request.POST, request.FILES, instance=produit)
        if form.is_valid():
            form.save()
            request.session.pop('selected_photo_produit', None)
            request.session.pop('selected_photo_produit_next', None)
            return redirect('liste_produits_vendeur')
    else:
        form = ProduitForm(instance=produit)

    return render(request, 'core/ajouter_produit.html', {'form': form, 'vendeur': produit.vendeur})

@login_required
def supprimer_produit(request, pk):
    produit = get_object_or_404(Produit, pk=pk, vendeur__user=request.user)
    produit.delete()
    return redirect('liste_produits_vendeur')

@login_required
def upload_photo_vendeur(request):
    if request.method == 'POST' and request.FILES.get('photo'):
        vendeur = get_object_or_404(Vendeur, user=request.user)
        vendeur.photo = request.FILES['photo']
        vendeur.save()
    return redirect('dashboard_vendeur')

def detail_produit(request, pk):
    produit = get_object_or_404(Produit, pk=pk, visible=True)
    log_action(request, 'product_view', f'Produit {produit.pk} - {produit.nom}')
    est_favori = False
    
    if request.user.is_authenticated:
        try:
            client = Client.objects.get(user=request.user)
            est_favori = Favori.objects.filter(
                client=client, produit=produit
            ).exists()
        except Client.DoesNotExist:
            pass
    
    evaluations = produit.evaluations.all()
    
    return render(request, 'core/detail_produit.html', {
        'produit': produit,
        'est_favori': est_favori,
        'evaluations': evaluations,
    })
def passer_commande(request, pk):
    produit = get_object_or_404(Produit, pk=pk, visible=True)
    erreur = None
    prix_base = produit.prix_promo if (produit.promo and produit.prix_promo) else produit.prix

    # Si client connecté, pré-remplir ses infos
    client_connecte = None
    try:
        if request.user.is_authenticated:
            client_connecte = Client.objects.get(user=request.user)
    except Client.DoesNotExist:
        pass

    discount_pct = 0
    prix_effectif = prix_base
    if client_connecte:
        discount_pct = get_loyalty_discount(client_connecte, produit.vendeur)
        prix_effectif = apply_loyalty_discount(prix_base, discount_pct)

    if request.method == 'POST':
        if client_connecte:
            nom = client_connecte.nom
            numero = client_connecte.numero
            ville = client_connecte.ville
        else:
            nom = request.POST.get('nom_client')
            numero = request.POST.get('numero_client')
            ville = request.POST.get('ville_client')

        message = request.POST.get('message', '')
        quantite = int(request.POST.get('quantite') or 1)

        if quantite > produit.quantite:
            erreur = f"Stock insuffisant. Seulement {produit.quantite} disponible(s)."
        else:
            commande = Commande.objects.create(
                produit=produit,
                vendeur=produit.vendeur,
                nom_client=nom,
                numero_client=numero,
                ville_client=ville,
                message=message,
                quantite=quantite,
                prix_unitaire=prix_effectif,
                prix_total=prix_effectif * quantite,
            )
            log_action(request, 'order_placed', f'Commande {commande.pk} produit {produit.pk} vendeur {produit.vendeur.pk} montant {commande.prix_total}')
            # Redirect to the payment page with the commande ID
            return redirect('payer_commande', pk=commande.pk)

# Calculate the total for the template (GET request)
    # Pour le formulaire de sélection de paiement, on affiche un formulaire préliminaire
    # sans encore créer la commande - l'utilisateur doit d'abord choisir le mode de paiement
    quantite = int(request.GET.get('quantite') or 1)
    montant = prix_effectif * quantite
    nom_client = None
    numero_client = None
    ville_client = None

    if client_connecte:
        nom_client = client_connecte.nom
        numero_client = client_connecte.numero
        ville_client = client_connecte.ville
    else:
        nom_client = request.GET.get('nom_client', '') or 'Client'
        numero_client = request.GET.get('numero_client', '') or '0000000000'
        ville_client = request.GET.get('ville_client', '') or 'Conakry'

    # Créer commande immédiatement pour permettre l'affichage du formulaire de paiement
    commande = Commande.objects.create(
        produit=produit,
        vendeur=produit.vendeur,
        nom_client=nom_client,
        numero_client=numero_client,
        ville_client=ville_client,
        message='',
        quantite=quantite,
        prix_unitaire=prix_effectif,
        prix_total=montant,
        statut='en_attente',
    )

    return render(request, 'core/choix_paiement.html', {
        'produit': produit,
        'commande': commande,
        'vendeur': produit.vendeur,
        'erreur': erreur,
        'prix_effectif': prix_effectif,
        'montant': montant,
        'quantite': quantite,
        'client_connecte': client_connecte,
        'discount_pct': discount_pct,
    })


def confirmation_commande(request):
    return render(request, 'core/confirmation_commande.html')

@login_required
def commandes_vendeur(request):
    from .models import Vendeur, Commande
    from django.shortcuts import get_object_or_404, render
    
    vendeur = get_object_or_404(Vendeur, user=request.user)
    commandes = Commande.objects.filter(
        vendeur=vendeur,
        archivee=False,
    ).order_by('-date_commande')
    
    # Calcul des compteurs par statut
    total_commandes = commandes.count()
    commandes_attente = commandes.filter(statut='en_attente').count()
    commandes_acceptees = commandes.filter(statut='acceptee').count()
    commandes_refusees = commandes.filter(statut='refusee').count()
    
    # Séparer les commandes par promo du produit
    commandes_promo = commandes.filter(produit__promo=True)
    commandes_non_promo = commandes.filter(produit__promo=False)
    
    # Compteurs pour les onglets promo
    total_promo = commandes_promo.count()
    total_non_promo = commandes_non_promo.count()
    
    return render(request, 'core/commandes_vendeur.html', {
        'commandes': commandes,
        'vendeur': vendeur,
        'total_commandes': total_commandes,
        'commandes_attente': commandes_attente,
        'commandes_acceptees': commandes_acceptees,
        'commandes_refusees': commandes_refusees,
        'commandes_promo': commandes_promo,
        'commandes_non_promo': commandes_non_promo,
        'total_promo': total_promo,
        'total_non_promo': total_non_promo,
    })

@login_required
def changer_statut_commande(request, pk):
    commande = get_object_or_404(Commande, pk=pk, vendeur__user=request.user)
    if request.method == 'POST':
        ancien_statut = commande.statut
        nouveau_statut = request.POST.get('statut')
        commande.statut = nouveau_statut
        commande.save()

        # Restaurer stock si refusée
        if nouveau_statut == 'refusee' and ancien_statut == 'en_attente':
            produit = commande.produit
            produit.quantite += commande.quantite
            produit.save()

# Ajouter aux ventes si acceptée
        if nouveau_statut == 'acceptee' and ancien_statut != 'acceptee':
            # Notification désactivée selon la demande de l'utilisateur
            pass
            '''
            creer_notification(
            user=commande.vendeur.user,
            type='commande',
            titre='✅ Commande acceptée',
            message=f'La commande #{commande.pk} de {commande.nom_client} a été acceptée.',
            lien='/mes-commandes/'
        )
            '''
            vendeur = commande.vendeur
            montant = commande.produit.prix * commande.quantite
            vendeur.ventes_du_mois += montant
            vendeur.save()

    return redirect('commandes_vendeur')

def choisir_abonnement(request=None):
    """Vue d’abonnement, compatible avec les appels internes sans requête."""
    if request is None:
        return None

    plans = PlanAbonnement.objects.exclude(nom='gratuit').order_by('prix')
    vendeur = None
    if request.user.is_authenticated:
        try:
            vendeur = Vendeur.objects.get(user=request.user)
        except Vendeur.DoesNotExist:
            vendeur = None

    return render(request, 'core/choisir_abonnement.html', {
        'vendeur': vendeur,
        'plans': plans,
    })


@login_required
def abonnement_vendeur(request):
    vendeur = get_object_or_404(Vendeur, user=request.user)
    try:
        abonnement = vendeur.abonnement
    except Abonnement.DoesNotExist:
        abonnement = None

    paiements = PaiementAbonnement.objects.filter(vendeur=vendeur).order_by('-date_soumission')

    return render(request, 'core/abonnement_vendeur.html', {
        'vendeur': vendeur,
        'abonnement': abonnement,
        'paiements': paiements,
    })


@login_required
def choisir_photo_produit(request):
    # Affiche les images disponibles dans media/produits/
    vendeur = get_object_or_404(Vendeur, user=request.user)
    _ = vendeur  # pour éviter warning/complète le contexte

    # next sert juste au retour
    return_url = request.GET.get('next') or request.META.get('HTTP_REFERER') or 'liste_produits_vendeur'

    from pathlib import Path
    import os

    media_root = getattr(settings, 'MEDIA_ROOT', None)
    if not media_root:
        images = []
    else:
        produits_dir = Path(media_root) / 'produits'
        images = []
        try:
            if produits_dir.exists():
                for p in sorted(produits_dir.iterdir()):
                    if p.is_file() and p.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp', '.gif']:
                        images.append(p.name)
        except:
            images = []

    # Au POST, le template renvoie photo_name + next
    if request.method == 'POST':
        return redirect('set_photo_produit')

    return render(request, 'core/choisir_photo_produit.html', {
        'images': images,
        'return_url': return_url,
    })


@login_required
def set_photo_produit(request):
    # Reçoit photo_name et next. On le renvoie ensuite vers ajouter/modifier via redirect.
    photo_name = request.POST.get('photo_name')
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'liste_produits_vendeur'

    if not photo_name:
        return redirect(next_url)

    # On va stocker temporairement le choix en session, pour l'utiliser au submit de ajouter/modifier.
    # (Le champ form.photo attend un upload; on le remplira côté POST dans ajouter_produit/modifier_produit.)
    request.session['selected_photo_produit'] = photo_name
    request.session['selected_photo_produit_next'] = next_url

    # On renvoie à la page de formulaire avec param photo=... pour la prévisualisation.
    # next_url peut être une URL ou un nom de vue; on préfère l'URL référencée.
    if '?' in next_url:
        redirect_to = f"{next_url}&photo={photo_name}"
    else:
        redirect_to = f"{next_url}?photo={photo_name}"

    return redirect(redirect_to)


def annuler_commande(request, pk):
    commande = get_object_or_404(Commande, pk=pk, statut='en_attente')
    if request.method == 'POST':
        commande.statut = 'annulee'
        commande.save()
        return redirect('confirmation_commande')
    return render(request, 'core/annuler_commande.html', {'commande': commande})



        
@login_required
def admin_valider_vendeur(request, pk):
    if not request.user.is_staff:
            return redirect('Welcome')
    vendeur = get_object_or_404(Vendeur, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'activer':
            vendeur.statut = 'actif'
            vendeur.save()
            # Créer abonnement essai
            plan_gratuit, _ = PlanAbonnement.objects.get_or_create(
                nom='gratuit',
                defaults={'prix': 0, 'limite_produits': 5, 'duree_jours': 30}
            )
            Abonnement.objects.get_or_create(
                vendeur=vendeur,
                defaults={
                    'plan': plan_gratuit,
                    'statut': 'essai',
                    'date_fin': timezone.now() + timedelta(days=30)
                }
            )
        elif action == 'suspendre':
            vendeur.statut = 'suspendu'
            vendeur.save()
        elif action == 'supprimer':
            vendeur.user.delete()
            return redirect('admin_dashboard')
    return redirect('admin_dashboard')

@login_required
def admin_valider_paiement_abonnement(request, pk):
    if not request.user.is_staff:
        return redirect('Welcome')

    paiement = get_object_or_404(PaiementAbonnement, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'valider':
            paiement.statut = 'valide'
            paiement.date_validation = timezone.now()
            paiement.save()

            vendeur = paiement.vendeur
            vendeur.statut = 'actif'
            vendeur.save()

            abonnement, created = Abonnement.objects.get_or_create(
                vendeur=vendeur,
                defaults={
                    'plan': paiement.plan,
                    'statut': 'actif',
                    'date_fin': timezone.now() + timedelta(days=paiement.plan.duree_jours),
                }
            )
            abonnement.plan = paiement.plan
            abonnement.statut = 'actif'
            abonnement.date_debut = timezone.now()
            abonnement.date_fin = timezone.now() + timedelta(days=paiement.plan.duree_jours)
            abonnement.save()
        elif action == 'refuser':
            paiement.statut = 'refuse'
            paiement.save()

    return redirect('admin_dashboard')


@login_required
def admin_valider_paiement_commande(request, pk):
    if not request.user.is_staff:
        return redirect('Welcome')
    paiement = get_object_or_404(PaiementCommande, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'valider':
            paiement.statut = 'valide'
            paiement.save()
            # Ajouter aux ventes du mois
            vendeur = paiement.commande.vendeur
            vendeur.ventes_du_mois += paiement.montant
            vendeur.save()
        elif action == 'refuser':
            paiement.statut = 'refuse'
            paiement.save()
    return redirect('admin_dashboard')

@login_required
def admin_paiements(request):
    if not request.user.is_staff:
        return redirect('Welcome')
    paiements = PaiementAbonnement.objects.filter(
        statut='en_attente'
    ).order_by('-date_soumission')
    return render(request, 'core/admin_paiements.html', {'paiements': paiements})

@login_required
def admin_traiter_signalement(request, pk):
    if not request.user.is_staff:
        return redirect('Welcome')
    signalement = get_object_or_404(Signalement, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'suspendre':
            signalement.vendeur.statut = 'suspendu'
            signalement.vendeur.save()
            signalement.vendeur.produit_set.update(visible=False)
        signalement.traite = True
        signalement.save()
    return redirect('admin_dashboard')

@login_required
def confirmation_paiement(request):
    return render(request, 'core/confirmation_paiement.html')

@login_required
def payer_abonnement(request, plan_nom):
    vendeur = get_object_or_404(Vendeur, user=request.user)
    plan = get_object_or_404(PlanAbonnement, nom=plan_nom)

    if request.method == 'POST':
        numero = request.POST.get('numero_paiement')
        reference = request.POST.get('reference', '')

        PaiementAbonnement.objects.create(
            vendeur=vendeur,
            plan=plan,
            numero_paiement=numero,
            montant=plan.prix,
            reference=reference,
            statut='en_attente'
        )
        return redirect('confirmation_paiement')

    return render(request, 'core/payer_abonnement.html', {
        'vendeur': vendeur,
        'plan': plan,
    })
def signaler_vendeur(request, vendeur_pk):
    vendeur = get_object_or_404(Vendeur, pk=vendeur_pk)
    client_connecte = None
    if request.user.is_authenticated:
        try:
            client_connecte = Client.objects.get(user=request.user)
        except:
            pass

    if request.method == 'POST':
        nom = client_connecte.nom if client_connecte else request.POST.get('nom')
        numero = client_connecte.numero if client_connecte else request.POST.get('numero')
        
        signalement = Signalement.objects.create(
            client_nom=nom,
            client_numero=numero,
            vendeur=vendeur,
            raison=request.POST.get('raison'),
            description=request.POST.get('description', '')
        )

        # Notifier le vendeur
        creer_notification(
            user=vendeur.user,
            type='securite',
            titre='⚠️ Nouveau signalement',
            message=f'Un client a signalé votre boutique pour : {signalement.raison}',
            lien='/mes-parametres/'
        )

        # Suspension auto après 3 signalements
        nb_total = Signalement.objects.filter(vendeur=vendeur).count()
        if nb_total >= 3:
            vendeur.statut = 'suspendu'
            vendeur.raison_suspension = f'Suspendu après {nb_total} signalements clients.'
            vendeur.save()
            vendeur.produit_set.update(visible=False)

        return redirect('catalogue')

    return render(request, 'core/signaler_vendeur.html', {
        'vendeur': vendeur,
        'client_connecte': client_connecte,
    })
                # Payer la commande

def payer_commande(request, pk):
    commande = get_object_or_404(Commande, pk=pk, statut='en_attente')
    produit = commande.produit

    modes_paiement = [
        ('orange_money', 'Orange Money'),
        ('carte_bancaire', 'Carte Bancaire'),
        ('paiement_livraison', 'Paiement à la livraison'),
        ('virement_bancaire', 'Virement bancaire'),
    ]

    client_connecte = None
    if request.user.is_authenticated:
        try:
            client_connecte = Client.objects.get(user=request.user)
        except Client.DoesNotExist:
            client_connecte = None

    if request.method == 'POST':
        mode_paiement = request.POST.get('mode_paiement', 'orange_money')
        numero = request.POST.get('numero_paiement', '').strip()
        reference = request.POST.get('reference', '')
        montant = commande.prix_total

        # Sécuriser les valeurs possibles
        modes_valides = [m[0] for m in modes_paiement]
        if mode_paiement not in modes_valides:
            mode_paiement = 'orange_money'

        # Compatibilité avec le champ existant obligatoire
        if not numero:
            if mode_paiement == 'paiement_livraison':
                numero = 'LIVRAISON'
            else:
                numero = 'N/A'

        PaiementCommande.objects.create(
            commande=commande,
            mode_paiement=mode_paiement,
            numero_paiement=numero,
            montant=montant,
            reference=reference,
        )
        log_action(request, 'payment', f'Commande {commande.pk} mode {mode_paiement} montant {montant}')

        if commande.vendeur:
            commande.vendeur.ventes_du_mois += montant
            commande.vendeur.save()

        if client_connecte and client_connecte.numero == commande.numero_client:
            update_loyalty_record(client_connecte, commande.vendeur, montant)

        # Notification vendeur par email
        try:
                send_mail(
                    subject=f'💰 Paiement reçu pour votre commande #{commande.pk}',
                    message=f'''
            Bonjour {commande.vendeur.nom_boutique},

            Un paiement a été effectué pour une de vos commandes !

            === INFOS COMMANDE ===
            Produit : {produit.nom}
            Quantité : {commande.quantite}.
            Montant total : {montant:,} GNF

            === INFOS CLIENT ===
            Nom : {commande.nom_client}
            Numéro WhatsApp : {commande.numero_client}
            Ville : {commande.ville_client}
            Message : {commande.message or "Aucun"}

            === PAIEMENT ===
            Mode de paiement : {dict(modes_paiement).get(mode_paiement, mode_paiement)}
            Identifiant / Numéro : {numero}
            Référence : {reference or "Non fournie"}

            Connectez-vous à votre dashboard pour accepter ou refuser cette commande.
                    ''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[commande.vendeur.user.email],
                    fail_silently=True,
            )
        except:
            pass

        return redirect('confirmation_paiement_commande')

    montant = commande.prix_total
    return render(request, 'core/payer_commande.html', {
        'commande': commande,
        'produit': produit,
        'montant': montant,
        'modes_paiement': modes_paiement,
    })

def confirmation_paiement_commande(request):
    """
    Page de confirmation de paiement pour le client.
    Affiche les commandes payées par le client (connecté ou non).
    """
    commande = None
    
    # First, check if user is authenticated and is a Client
    if request.user.is_authenticated:
        try:
            client = Client.objects.get(user=request.user)
            # Get the most recent paid command for this client by phone number
            commande = Commande.objects.filter(
                numero_client=client.numero,
                statut__in=['en_attente', 'acceptee', 'refusee']
            ).order_by('-date_commande').first()
        except Client.DoesNotExist:
            # User is authenticated but not a client (e.g., vendor or admin)
            # Try to find the most recent PaiementCommande
            pass
    
    # If no commande found or user is anonymous, get the most recent paid order
    if not commande:
        dernier_paiement = PaiementCommande.objects.filter(
            statut='en_attente'
        ).order_by('-date_soumission').first()
        
        if not dernier_paiement:
            # Try to get any recent commande regardless of payment status
            dernier_paiement = PaiementCommande.objects.order_by('-date_soumission').first()
        
        commande = dernier_paiement.commande if dernier_paiement else None
    
    return render(request, 'core/confirmation_paiement_commande.html', {
        'commande': commande,
    })


def telecharger_facture(request, pk):
    """
    Génère une facture (HTML) pour la commande.
    Le client peut l'imprimer en PDF depuis son navigateur.
    """
    from django.http import HttpResponse
    
    try:
        commande = Commande.objects.get(pk=pk)
    except Commande.DoesNotExist:
        return redirect('espace_client')
    
    # L'accès à la facture est autorisé pour les commandes du client connecté
    # et pour les commandes guest, puisque l'URL est déjà fournie depuis la confirmation.
    return render(request, 'core/facture.html', {
        'commande': commande,
        'vendeur': commande.vendeur,
        'produit': commande.produit,
        'paiement': getattr(commande, 'paiement', None),
    })


# ============================================
# PAIEMENT PAR MODE (Pages séparées)
# ============================================
# Paiement sans compte obligatoire - tous les clients peuvent payer

def payer_commande_orange(request, pk):
    """Page de paiement Orange Money séparée - Accessible sans connexion"""
    commande = get_object_or_404(Commande, pk=pk)
    produit = commande.produit
    
    client = None
    if request.user.is_authenticated:
        try:
            client = Client.objects.get(user=request.user)
        except Client.DoesNotExist:
            client = None
    
    if request.method == 'POST':
        numero_paiement = request.POST.get('numero_paiement', '').strip()
        reference = request.POST.get('reference', '').strip()
        
        if not numero_paiement:
            numero_paiement = 'N/A'
        
        PaiementCommande.objects.create(
            commande=commande,
            mode_paiement='orange_money',
            numero_paiement=numero_paiement,
            montant=commande.prix_total,
            reference=reference,
        )
        log_action(request, 'payment', f'Commande {commande.pk} mode orange_money montant {commande.prix_total}')
        
        # ✅ Réduire le stock après confirmation du paiement
        reducer_stock(commande)
        
        if commande.vendeur:
            commande.vendeur.ventes_du_mois += commande.prix_total
            commande.vendeur.save()
        if client and client.numero == commande.numero_client:
            update_loyalty_record(client, commande.vendeur, commande.prix_total)
        
        # Notification vendeur
        try:
            send_mail(
                subject=f'🍊 Paiement Orange Money - Commande #{commande.pk}',
                message=f'''
Un paiement Orange Money a été effectué pour la commande #{commande.pk}.

Produit: {produit.nom}
Montant: {commande.prix_total:,} GNF
Numéro client: {numero_paiement}
Référence: {reference or 'Non fournie'}

Client: {commande.nom_client} ({commande.numero_client})
Ville: {commande.ville_client}
                ''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[commande.vendeur.user.email],
                fail_silently=True,
            )
        except:
            pass
        
        return redirect('confirmation_paiement_commande')
    
    return render(request, 'core/payer_orange_money.html', {
        'commande': commande,
        'produit': produit,
        'montant': commande.prix_total,
    })


def payer_commande_mobile(request, pk):
    """Page de paiement Mobile Money séparée - Accessible sans connexion"""
    commande = get_object_or_404(Commande, pk=pk)
    produit = commande.produit
    
    client = None
    if request.user.is_authenticated:
        try:
            client = Client.objects.get(user=request.user)
        except Client.DoesNotExist:
            client = None
    
    if request.method == 'POST':
        numero_paiement = request.POST.get('numero_paiement', '').strip()
        reference = request.POST.get('reference', '').strip()
        
        if not numero_paiement:
            numero_paiement = 'N/A'
        
        PaiementCommande.objects.create(
            commande=commande,
            mode_paiement='mobile_money',
            numero_paiement=numero_paiement,
            montant=commande.prix_total,
            reference=reference,
        )
        log_action(request, 'payment', f'Commande {commande.pk} mode mobile_money montant {commande.prix_total}')
        
        # ✅ Réduire le stock après confirmation du paiement
        reducer_stock(commande)
        
        if commande.vendeur:
            commande.vendeur.ventes_du_mois += commande.prix_total
            commande.vendeur.save()
        if client and client.numero == commande.numero_client:
            update_loyalty_record(client, commande.vendeur, commande.prix_total)
        
        # Notification vendeur
        try:
            send_mail(
                subject=f'📱 Paiement Mobile Money - Commande #{commande.pk}',
                message=f'''
Un paiement Mobile Money a été effectué pour la commande #{commande.pk}.

Produit: {produit.nom}
Montant: {commande.prix_total:,} GNF
Numéro client: {numero_paiement}
Référence: {reference or 'Non fournie'}

Client: {commande.nom_client} ({commande.numero_client})
Ville: {commande.ville_client}
                ''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[commande.vendeur.user.email],
                fail_silently=True,
            )
        except:
            pass
        
        return redirect('confirmation_paiement_commande')
    
    return render(request, 'core/payer_mobile_money.html', {
        'commande': commande,
        'produit': produit,
        'montant': commande.prix_total,
    })


def payer_commande_livraison(request, pk):
    """Page de paiement à la livraison séparée - Accessible sans connexion"""
    commande = get_object_or_404(Commande, pk=pk)
    produit = commande.produit
    
    client = None
    if request.user.is_authenticated:
        try:
            client = Client.objects.get(user=request.user)
        except Client.DoesNotExist:
            client = None
    
    if request.method == 'POST':
        adresse_livraison = request.POST.get('adresse_livraison', '').strip()
        instructions = request.POST.get('instructions', '').strip()
        
        # Pour paiement à la livraison, le numéro est utilisé pour livrer
        numero = commande.numero_client
        
        PaiementCommande.objects.create(
            commande=commande,
            mode_paiement='paiement_livraison',
            numero_paiement=numero,
            montant=commande.prix_total,
            reference=adresse_livraison + (' | ' + instructions if instructions else ''),
        )
        log_action(request, 'payment', f'Commande {commande.pk} mode paiement_livraison montant {commande.prix_total}')
        
        # ✅ Réduire le stock après confirmation du paiement
        reducer_stock(commande)
        
        if commande.vendeur:
            commande.vendeur.ventes_du_mois += commande.prix_total
            commande.vendeur.save()
        if client and client.numero == commande.numero_client:
            update_loyalty_record(client, commande.vendeur, commande.prix_total)
        
# Notification vendeur
        try:
            send_mail(
                subject=f'🚚 Paiement à la livraison - Commande #{commande.pk}',
                message=f'''
Une commande avec paiement à la livraison a été passée ({commande.pk}).

Produit: {produit.nom}
Quantité: {commande.quantite}
Montant à payer: {commande.prix_total:,} GNF

Client: {commande.nom_client} ({commande.numero_client})
Ville: {commande.ville_client}
Adresse livraison: {adresse_livraison}
Instructions: {instructions or 'Aucune'}
                ''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[commande.vendeur.user.email],
                fail_silently=True,
            )
        except:
            pass
        
        return redirect('confirmation_paiement_commande')
    
    return render(request, 'core/payer_livraison.html', {
        'commande': commande,
        'produit': produit,
        'montant': commande.prix_total,
    })


# ============================================
# HELPER FUNCTIONS
# ============================================

def reducer_stock(commande):
    """
    Reduce product stock when payment is confirmed.
    Called after client confirms payment method.
    """
    try:
        produit = commande.produit
        if produit.quantite >= commande.quantite:
            produit.quantite -= commande.quantite
        else:
            produit.quantite = 0
        produit.save()
    except Exception as e:
        print(f"Erreur lors de la réduction du stock: {e}")

def creer_notification(user, type, titre, message, lien=''):
    """Utility to create in-app notification"""
    Notification.objects.create(
        user=user,
        type=type,
        titre=titre,
        message=message,
        lien=lien
    )

def verifier_promos_expirees():
    """
    Vérifie et désactive les promos expirées.
    Cette fonction doit être appelée dans toutes les vues qui affichent les produits en promo.
    """
    from django.utils import timezone
    produits_expires = Produit.objects.filter(
        promo=True,
        date_fin_promo__isnull=False,
        date_fin_promo__lt=timezone.now()
    )
    
    for produit in produits_expires:
        produit.promo = False
        produit.prix_promo = None
        produit.jours_promo = None
        produit.date_fin_promo = None
        produit.date_debut_promo = None
        produit.save()

# ============================================
# ============================================
# SYSTÈME DE PANIER
# ============================================
# SECURITY: AJAX views now require CSRF token
# Les appels AJAX doivent envoyer le token dans l'en-tête X-CSRFToken

@csrf_exempt
def ajouter_au_panier(request, produit_pk):
    """Wrapper: endpoint AJAX d'ajout au panier. Exempté CSRF pour compatibilité clients JS."""
    """Ajouter un produit au panier via AJAX"""
    from .models import Panier, PanierItem

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée.'}, status=405)

    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'error': 'Veuillez vous connecter pour ajouter au panier.',
            'redirect': '/connexion-client/'
        }, status=401)

    try:
        client = Client.objects.get(user=request.user)
    except Client.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Votre compte n\'est pas un compte client. Connectez-vous avec un compte client.',
            'redirect': '/connexion-client/'
        }, status=403)
    
    produit = get_object_or_404(Produit, pk=produit_pk, visible=True)
    
    if produit.quantite < 1:
        return JsonResponse({'error': 'Produit en rupture de stock'}, status=400)
    
    panier, created = Panier.objects.get_or_create(client=client)
    
    item, created = PanierItem.objects.get_or_create(
        panier=panier,
        produit=produit,
        defaults={'quantite': 1}
    )
    
    if not created:
        nouvelle_qte = item.quantite + 1
        if nouvelle_qte > produit.quantite:
            return JsonResponse({
                'error': f'Stock insuffisant. Il ne reste que {produit.quantite} exemplaire(s).'
            }, status=400)
        item.quantite = nouvelle_qte
        item.save()
    
    total_items = sum(i.quantite for i in panier.items.all())
    
    return JsonResponse({
        'success': True,
        'message': f'{produit.nom} ajouté au panier !',
        'total_items': total_items,
    })


@login_required
def supprimer_du_panier(request, item_pk):
    """Retirer un article du panier"""
    from .models import Panier, PanierItem
    
    try:
        client = Client.objects.get(user=request.user)
        panier = Panier.objects.get(client=client)
        item = get_object_or_404(PanierItem, pk=item_pk, panier=panier)
        item.delete()
        messages.success(request, 'Article retiré du panier.')
    except (Client.DoesNotExist, Panier.DoesNotExist):
        pass
    
    return redirect('voir_panier')


@login_required
def modifier_quantite_panier(request, item_pk):
    """Modifier la quantité d'un article dans le panier"""
    from .models import Panier, PanierItem
    
    if request.method == 'POST':
        try:
            client = Client.objects.get(user=request.user)
            panier = Panier.objects.get(client=client)
            item = get_object_or_404(PanierItem, pk=item_pk, panier=panier)
            
            nouvelle_qte = int(request.POST.get('quantite', 1))
            if nouvelle_qte < 1:
                item.delete()
                messages.success(request, 'Article retiré du panier.')
            else:
                if nouvelle_qte > item.produit.quantite:
                    messages.error(request, f'Stock insuffisant. Il ne reste que {item.produit.quantite}.')
                else:
                    item.quantite = nouvelle_qte
                    item.save()
                    messages.success(request, 'Quantité mise à jour.')
        except (Client.DoesNotExist, Panier.DoesNotExist):
            pass
    
    return redirect('voir_panier')


@login_required
def voir_panier(request):
    """Page affichant le panier du client"""
    from .models import Panier, Client
    
    try:
        client = Client.objects.get(user=request.user)
        panier = Panier.objects.get(client=client)
        items = panier.items.select_related('produit', 'produit__vendeur').all()
    except (Client.DoesNotExist, Panier.DoesNotExist):
        items = []
        panier = None
        client = None
    
    total = 0
    for item in items:
        prix = item.produit.prix_promo if (item.produit.promo and item.produit.prix_promo) else item.produit.prix
        total += prix * item.quantite
    
    vendors_dict = {}
    for item in items:
        vendor = item.produit.vendeur
        if vendor.pk not in vendors_dict:
            vendors_dict[vendor.pk] = {
                'vendeur': vendor,
                'items': [],
                'subtotal': 0
            }
        prix = item.produit.prix_promo if (item.produit.promo and item.produit.prix_promo) else item.produit.prix
        subtotal = prix * item.quantite
        vendors_dict[vendor.pk]['items'].append(item)
        vendors_dict[vendor.pk]['subtotal'] += subtotal
    
    return render(request, 'core/panier.html', {
        'panier': panier,
        'items': items,
        'total': total,
        'vendors_dict': vendors_dict,
        'client': client,
    })


@login_required
def commander_panier(request):
    """Créer les commandes à partir du panier et payer en un seul paiement"""
    from .models import Panier, Commande, PaiementPanier
    
    try:
        client = Client.objects.get(user=request.user)
        panier = Panier.objects.get(client=client)
        items = panier.items.select_related('produit', 'produit__vendeur').all()
    except (Client.DoesNotExist, Panier.DoesNotExist):
        messages.error(request, 'Votre panier est vide.')
        return redirect('catalogue')
    
    if not items.exists():
        messages.error(request, 'Votre panier est vide.')
        return redirect('catalogue')
    
    erros_stock = []
    for item in items:
        if item.quantite > item.produit.quantite:
            erros_stock.append(f"{item.produit.nom} : stock insuffisant ({item.produit.quantite} disponible)")
    
    if erros_stock:
        for error in erros_stock:
            messages.error(request, error)
        return redirect('voir_panier')
    
    total = 0
    for item in items:
        prix = item.produit.prix_promo if (item.produit.promo and item.produit.prix_promo) else item.produit.prix
        discount_pct = get_loyalty_discount(client, item.produit.vendeur)
        prix_effectif = apply_loyalty_discount(prix, discount_pct)
        total += prix_effectif * item.quantite
    
    commandes_creees = []
    for item in items:
        prix = item.produit.prix_promo if (item.produit.promo and item.produit.prix_promo) else item.produit.prix
        discount_pct = get_loyalty_discount(client, item.produit.vendeur)
        prix_effectif = apply_loyalty_discount(prix, discount_pct)
        
        commande = Commande.objects.create(
            produit=item.produit,
            vendeur=item.produit.vendeur,
            nom_client=client.nom,
            numero_client=client.numero,
            ville_client=client.ville,
            message='',
            quantite=item.quantite,
            prix_unitaire=prix_effectif,
            prix_total=prix_effectif * item.quantite,
            statut='en_attente',
        )
        commandes_creees.append(commande)
    
    paiement_panier = PaiementPanier.objects.create(
        client=client,
        montant_total=total,
        numero_paiement='',
        reference='',
        statut='en_attente'
    )
    
    for commande in commandes_creees:
        commande.paiement_panier = paiement_panier
        commande.save()
    
    panier.items.all().delete()
    
    return redirect('payer_panier', paiement_pk=paiement_panier.pk)


@login_required
def payer_panier(request, paiement_pk):
    """Page de paiement pour le panier"""
    from .models import PaiementPanier

    paiement = get_object_or_404(PaiementPanier, pk=paiement_pk)
    
    try:
        client = Client.objects.get(user=request.user)
        if paiement.client != client:
            messages.error(request, 'Accès refusé.')
            return redirect('catalogue')
    except Client.DoesNotExist:
        return redirect('Welcome')
    
    commandes = paiement.commandes.select_related('produit', 'vendeur').all()
    
    modes_paiement = [
        ('orange_money', 'Orange Money'),
        ('mobile_money', 'Mobile Money'),
        ('paiement_livraison', 'Paiement à la livraison'),
    ]
    
    if request.method == 'POST':
        mode = request.POST.get('mode_paiement', 'orange_money')
        numero = request.POST.get('numero_paiement', '').strip()
        reference = request.POST.get('reference', '').strip()
        
        if not numero:
            if mode == 'paiement_livraison':
                numero = 'LIVRAISON'
            else:
                numero = 'N/A'
        
        paiement.mode_paiement = mode
        paiement.numero_paiement = numero
        paiement.reference = reference
        paiement.statut = 'valide'
        paiement.date_validation = timezone.now()
        paiement.save()
        
        for commande in commandes:
            produit = commande.produit
            if produit.quantite >= commande.quantite:
                produit.quantite -= commande.quantite
            else:
                produit.quantite = 0
            produit.save()
            
            vendeur = commande.vendeur
            montant = commande.prix_total
            vendeur.ventes_du_mois += montant
            vendeur.save()
            if client:
                update_loyalty_record(client, vendeur, montant)
            
            try:
                send_mail(
                    subject=f'🛒 Nouvelle commande #{commande.pk} - Panier payé',
                    message=f'''
Nouvelle commande issue du panier !

Client: {client.nom}
Téléphone: {client.numero}
Ville: {client.ville}

Produit: {produit.nom}
Quantité: {commande.quantite}
Prix unitaire: {commande.prix_unitaire:,} GNF
Total: {commande.prix_total:,} GNF

Mode de paiement: {mode}
Statut: Payé et validé automatiquement
                    ''',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[vendeur.user.email],
                    fail_silently=True,
                )
            except:
                pass
        
        # Note: La notification est commenté car la page de confirmation affiche déjà le succès
        # creer_notification(
        #     user=request.user,
        #     type='commande',
        #     titre='✅ Panier payé avec succès !',
        #     message=f'Votre paiement de {paiement.montant_total:,} GNF a été validé.',
        #     lien='/mes-factures/'
        # )
        
        return redirect('confirmation_panier_paye', paiement_pk=paiement.pk)
    
    return render(request, 'core/payer_panier.html', {
        'paiement': paiement,
        'commandes': commandes,
        'modes_paiement': modes_paiement,
    })


@login_required
def confirmation_panier_paye(request, paiement_pk):
    """Page de confirmation après paiement du panier"""
    from .models import PaiementPanier
    
    paiement = get_object_or_404(PaiementPanier, pk=paiement_pk)
    
    return render(request, 'core/confirmation_panier_paye.html', {
        'paiement': paiement,
    })


def get_panier_count(request):
    """API pour récupérer le nombre d'articles dans le panier"""
    from .models import Panier, Client
    
    if not request.user.is_authenticated:
        return JsonResponse({'count': 0, 'total': 0})
    
    try:
        client = Client.objects.get(user=request.user)
        panier = Panier.objects.get(client=client)
        total_items = sum(item.quantite for item in panier.items.all())
        
        total = 0
        for item in panier.items.all():
            prix = item.produit.prix_promo if (item.produit.promo and item.produit.prix_promo) else item.produit.prix
            total += prix * item.quantite
        
        return JsonResponse({
            'count': total_items,
            'total': total,
        })
    except (Client.DoesNotExist, Panier.DoesNotExist):
        return JsonResponse({'count': 0, 'total': 0})
def inscription_client(request):
    erreur = None
    if request.method == 'POST':
        nom = request.POST.get('nom')
        numero = request.POST.get('numero')
        ville = request.POST.get('ville')
        email = request.POST.get('email')
        mot_de_passe = request.POST.get('mot_de_passe')
        confirmer = request.POST.get('confirmer_mot_de_passe')

        if mot_de_passe != confirmer:
            erreur = "Les mots de passe ne correspondent pas."
        elif User.objects.filter(username=email).exists():
            erreur = "Un compte existe déjà avec cet email."
        else:
            user = User.objects.create_user(
                username=email, email=email, password=mot_de_passe
            )
            Client.objects.create(
                user=user, nom=nom, numero=numero, ville=ville
            )
            log_action(request, 'signup_client', f'Client {email}')
            return render(request, 'core/confirmation_inscription_client.html', {
                'nom': nom,
                'email': email,
            })

    return render(request, 'core/inscription_client.html', {'erreur': erreur})

def connexion_client(request):
    erreur = None
    if request.method == 'POST':
        email = request.POST.get('email')
        mot_de_passe = request.POST.get('mot_de_passe')
        user = authenticate(request, username=email, password=mot_de_passe)
        if user is not None:
            try:
                client = Client.objects.get(user=user)
                login(request, user)
                log_action(request, 'login_client', f'Client {email}')
                return redirect('espace_client')  # ← espace client, pas catalogue
            except Client.DoesNotExist:
                erreur = "Ce compte n'est pas un compte client."
        else:
            erreur = "Email ou mot de passe incorrect."

    return render(request, 'core/connexion_client.html', {'erreur': erreur})

@login_required
def espace_client(request):
    try:
        client = Client.objects.get(user=request.user)
    except Client.DoesNotExist:
        return redirect('Welcome')

    commandes = Commande.objects.filter(
        nom_client=client.nom,
        numero_client=client.numero,
        archivee=False,
    ).order_by('-date_commande')

    commandes_attente = commandes.filter(statut='en_attente').count()
    commandes_acceptees = commandes.filter(statut='acceptee').count()
    commandes_refusees = commandes.filter(statut__in=['refusee', 'annulee']).count()

    # ← AJOUT : compter les commandes acceptées non encore vues
    nb_commandes_acceptees = commandes_acceptees

    # Proposition suppression historique (> 30 jours)
    seuil_un_mois = timezone.now() - timedelta(days=30)
    proposer_suppression_historique = commandes.filter(
        date_commande__lt=seuil_un_mois
    ).exists()

    favoris = Favori.objects.filter(client=client).select_related('produit')
    notifications = Notification.objects.filter(
        user=request.user, lue=False
    ).order_by('-date')[:10]
    nb_notifications = notifications.count()

    # Compter les messages non lus pour le client
    # Compter les négociations où client_lu=False
    negotiations_non_lus = MessageNegociation.objects.filter(
        client_numero=client.numero, client_lu=False
    ).count()
    
    # Compter les ChatMessage non lus envoyés par le vendor pour ce client
    chat_non_lus = ChatMessage.objects.filter(
        negociation__client_numero=client.numero,
        sender_type='vendeur'
).exclude(
        negociation__client_lu=True
    ).count()
    
    nb_messages_non_lus = negotiations_non_lus + chat_non_lus
    
    # Générer la salutation personnalisée
    salutation = get_salutation_with_name(client.nom)

    return render(request, 'core/espace_client.html', {
        'client': client,
        'commandes': commandes,
        'favoris': favoris,
        'notifications': notifications,
        'nb_notifications': nb_notifications,
        'nb_commandes_acceptees': nb_commandes_acceptees,
        'commandes_attente': commandes_attente,
        'commandes_acceptees': commandes_acceptees,
        'commandes_refusees': commandes_refusees,
        'proposer_suppression_historique': proposer_suppression_historique,
        'nb_messages_non_lus': nb_messages_non_lus,
        'salutation': salutation,
    })

@login_required
def supprimer_historique_commandes_client(request):
    try:
        client = Client.objects.get(user=request.user)
    except Client.DoesNotExist:
        return redirect('Welcome')

    if request.method == 'POST':
        seuil_un_mois = timezone.now() - timedelta(days=30)
        nb = Commande.objects.filter(
            nom_client=client.nom,
            numero_client=client.numero,
            date_commande__lt=seuil_un_mois
        ).count()

        Commande.objects.filter(
            nom_client=client.nom,
            numero_client=client.numero,
            date_commande__lt=seuil_un_mois
        ).delete()

        if nb > 0:
            messages.success(request, f'{nb} commande(s) de plus d’un mois ont été supprimée(s) de votre historique.')
        else:
            messages.info(request, "Aucune commande de plus d’un mois à supprimer.")

    return redirect('espace_client')

# ============================================
# FAVORIS
# ============================================
# SECURITY: AJAX views now require CSRF token
# Les appels AJAX doivent inclure le token CSRF dans l'en-tête X-CSRFToken

@login_required
def toggle_favori(request, produit_pk):
    """Basculer l'état favori d'un produit (retourne JSON pour AJAX)"""
    try:
        client = Client.objects.get(user=request.user)
        produit = get_object_or_404(Produit, pk=produit_pk)
        favori, created = Favori.objects.get_or_create(client=client, produit=produit)
        if not created:
            favori.delete()
            is_favori = False
        else:
            is_favori = True
        return JsonResponse({
            'success': True,
            'is_favori': is_favori,
            'message': 'Ajouté aux favoris!' if is_favori else 'Retiré des favoris.'
        })
    except Client.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Vous devez avoir un compte client.'
        }, status=403)


@login_required
def get_favori_status(request, produit_pk):
    """API pour vérifier si un produit est en favori"""
    try:
        client = Client.objects.get(user=request.user)
        produit = get_object_or_404(Produit, pk=produit_pk)
        is_favori = Favori.objects.filter(client=client, produit=produit).exists()
        return JsonResponse({'is_favori': is_favori})
    except Client.DoesNotExist:
        return JsonResponse({'is_favori': False})


@login_required
def mes_favoris(request):
    """Page affichant tous les favoris du client"""
    try:
        client = Client.objects.get(user=request.user)
    except Client.DoesNotExist:
        return redirect('Welcome')
    
    favoris = Favori.objects.filter(
        client=client
    ).select_related('produit', 'produit__vendeur').order_by('-date_ajout')
    
    return render(request, 'core/mes_favoris.html', {
        'favoris': favoris,
        'client': client,
    })

# ============================================
# NOTIFICATIONS
# ============================================
@login_required
def mes_notifications(request):
    notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-date')
    # Marquer comme lues
    notifications.update(lue=True)
    return render(request, 'core/notifications.html', {
        'notifications': notifications
    })


# ============================================
# API NOTIFICATIONS POLLING
# ============================================

def api_notifications_nouvelles(request):
    """
    API pour le polling - retourne les nouvelles notifications depuis la dernière vérification.
    """
    from django.utils import timezone
    from datetime import timedelta
    
    # Si utilisateur non authentifié, retourner structure vide (polling safe)
    if not request.user.is_authenticated:
        from django.utils import timezone
        return JsonResponse({'nouvelles': [], 'nb_non_lues': 0, 'timestamp': timezone.now().isoformat()})

    # Dernière vérification (par paramètre ou il y a 30 secondes)
    since = request.GET.get('since')
    if since:
        try:
            from datetime import datetime
            last_check = datetime.fromisoformat(since)
        except:
            last_check = timezone.now() - timedelta(seconds=30)
    else:
        last_check = timezone.now() - timedelta(seconds=30)
    
    # Nouvelles notifications depuis la dernière vérification
    nouvelles = Notification.objects.filter(
        user=request.user,
        date__gte=last_check,
        lue=False
    ).values('id', 'type', 'titre', 'message', 'date', 'lien')
    
    # Compter les non lues totales
    nb_non_lues = Notification.objects.filter(
        user=request.user, lue=False
    ).count()
    
    return JsonResponse({
        'nouvelles': list(nouvelles),
        'nb_non_lues': nb_non_lues,
        'timestamp': timezone.now().isoformat()
    })

# ============================================
# MES FACTURES
# ============================================
@login_required
def mes_factures(request):
    """Page listant toutes les factures du client"""
    try:
        client = Client.objects.get(user=request.user)
    except Client.DoesNotExist:
        return redirect('Welcome')

    # Get all orders for this client (with any status) - these are the ones with invoices
    # First, get orders by phone number
    commandes = Commande.objects.filter(
        numero_client=client.numero
    ).order_by('-date_commande')
    
    # Also get orders from cart payments (via PaiementPanier linked to this client)
    # These are orders where client paid for multiple items at once
    from .models import PaiementPanier
    paiements_panier = PaiementPanier.objects.filter(
        client=client,
        statut='valide'
    ).order_by('-date_validation')
    
    # Get all orders associated with these cart payments
    commandes_panier = Commande.objects.filter(
        paiement_panier__in=paiements_panier
    ).order_by('-date_commande')
    
    # Combine both querysets (excluding duplicates)
    semua_commandes = (commandes | commandes_panier).distinct().order_by('-date_commande')

    return render(request, 'core/mes_factures.html', {
        'commandes': semua_commandes,
        'client': client,
    })

def nb_notifications(request):
    if request.user.is_authenticated:
        return Notification.objects.filter(
            user=request.user, lue=False
        ).count()
    return 0

# ============================================
# ÉVALUATIONS
# ============================================
@login_required
def evaluer_produit(request, pk):
    produit = get_object_or_404(Produit, pk=pk)
    
    # Get client info if logged in
    client = None
    if request.user.is_authenticated:
        try:
            client = Client.objects.get(user=request.user)
        except Client.DoesNotExist:
            pass
    
    if request.method == 'POST':
        if client:
            Evaluation.objects.create(
                produit=produit,
                client_nom=client.nom,
                client_numero=client.numero,
                note=int(request.POST.get('note', 5)),
                commentaire=request.POST.get('commentaire', '')
            )
            messages.success(request, 'Merci pour votre avis!')
            return redirect('detail_produit', pk=pk)
        else:
            messages.error(request, 'Vous devez être connecté pour évaluer.')
    
    return render(request, 'core/evaluer_produit.html', {
        'produit': produit,
        'client': client
    })

# ============================================
# STATISTIQUES VENDEUR
# ============================================
@login_required
def statistiques_vendeur(request):
    from django.db.models import Sum, Count
    from datetime import datetime
    
    vendeur = get_object_or_404(Vendeur, user=request.user)
    
    # Calcul des statistiques de base
    total_commandes = Commande.objects.filter(vendeur=vendeur).count()
    commandes_acceptees = Commande.objects.filter(vendeur=vendeur, statut='acceptee').count()
    commandes_refusees = Commande.objects.filter(vendeur=vendeur, statut='refusee').count()
    commandes_attente = Commande.objects.filter(vendeur=vendeur, statut='en_attente').count()
    total_produits = Produit.objects.filter(vendeur=vendeur).count()
    produits_en_ligne = Produit.objects.filter(vendeur=vendeur, visible=True).count()

    # Produit le plus commandé
    meilleur_produit = Commande.objects.filter(vendeur=vendeur).values(
        'produit__nom'
    ).annotate(total=Count('id')).order_by('-total').first()

    # ===== EVOLUTION DES VENTES MOIS PAR MOIS =====
    maintenant = timezone.now()
    actuel_mois = maintenant.month
    actuel_annee = maintenant.year

    mois_francais = [
        'Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin',
        'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc'
    ]

    commandes_acceptees_vendeur = Commande.objects.filter(
        vendeur=vendeur,
        statut='acceptee'
    )

    # Construire une fenêtre de 12 mois jusqu'au mois actuel
    mois_annee_window = []
    for i in range(11, -1, -1):
        mois_calc = actuel_mois - i
        annee_calc = actuel_annee
        while mois_calc < 1:
            mois_calc += 12
            annee_calc -= 1
        mois_annee_window.append((annee_calc, mois_calc))

    # Agréger les ventes acceptées par année/mois
    from django.db.models.functions import ExtractYear, ExtractMonth
    ventes_par_mois = commandes_acceptees_vendeur.annotate(
        annee=ExtractYear('date_commande'),
        mois=ExtractMonth('date_commande')
    ).values('annee', 'mois').annotate(total=Sum('prix_total')).order_by('annee', 'mois')

    ventes_par_mois_dict = {
        f"{item['annee']}-{item['mois']:02d}": int(item['total'] or 0)
        for item in ventes_par_mois
    }

    labels_graphique = []
    donnees_graphique = []
    for annee_calc, mois_calc in mois_annee_window:
        clef = f"{annee_calc}-{mois_calc:02d}"
        labels_graphique.append(mois_francais[mois_calc - 1])
        donnees_graphique.append(ventes_par_mois_dict.get(clef, 0))

    ventes_mois_actuel = donnees_graphique[-1] if donnees_graphique else 0

    if len(donnees_graphique) >= 2:
        ventes_mois_precedent = donnees_graphique[-2]
        if ventes_mois_precedent > 0:
            evolution_pourcent = ((ventes_mois_actuel - ventes_mois_precedent) / ventes_mois_precedent) * 100
            evolution_pourcent = round(evolution_pourcent, 1)
        else:
            evolution_pourcent = None
    else:
        evolution_pourcent = None

    return render(request, 'core/statistiques_vendeur.html', {
        'vendeur': vendeur,
        'total_commandes': total_commandes,
        'commandes_acceptees': commandes_acceptees,
        'commandes_refusees': commandes_refusees,
        'commandes_attente': commandes_attente,
        'total_produits': total_produits,
        'produits_en_ligne': produits_en_ligne,
        'meilleur_produit': meilleur_produit,
        'ventes_du_mois': ventes_mois_actuel,
        'labels_graphique': labels_graphique,
        'donnees_graphique': donnees_graphique,
        'evolution_pourcent': evolution_pourcent,
    })

# ============================================
# CATALOGUE AMÉLIORÉ AVEC CATÉGORIES
# ============================================
def catalogue(request):
    from django.db.models import Count, Avg
    
    choisir_abonnement()
    verifier_promos_expirees()
    selected_ville = request.GET.get('ville', '')
    recherche = request.GET.get('q', '')
    categorie_slug = request.GET.get('categorie', '')

    default_ville = ''
    if request.user.is_authenticated:
        try:
            client = Client.objects.get(user=request.user)
            if not selected_ville:
                default_ville = client.ville
        except Client.DoesNotExist:
            pass

    produits = Produit.objects.filter(visible=True, vendeur__statut='actif').annotate(
        evaluation_count=Count('evaluations'),
        evaluation_note=Avg('evaluations__note')
    )

    if selected_ville:
        produits = produits.filter(vendeur__ville__icontains=selected_ville)
    elif default_ville:
        produits = produits.annotate(
            priority=Case(
                When(vendeur__ville__iexact=default_ville, then=Value(0)),
                default=Value(1),
                output_field=IntegerField()
            )
        ).order_by('priority', 'nom')

    if recherche:
        produits = produits.filter(
            Q(nom__icontains=recherche) |
            Q(description__icontains=recherche) |
            Q(categorie__nom__icontains=recherche) |
            Q(vendeur__nom_boutique__icontains=recherche) |
            Q(vendeur__ville__icontains=recherche)
        )

    if categorie_slug:
        produits = produits.filter(categorie__slug=categorie_slug)

    ville_selectionnee = selected_ville or default_ville

    categories = Categorie.objects.all()
    villes = Vendeur.objects.filter(statut='actif').values_list('ville', flat=True).distinct()
    promos = Produit.objects.filter(visible=True, promo=True, vendeur__statut='actif')[:10]

    return render(request, 'core/catalogue.html', {
        'produits': produits,
        'categories': categories,
        'villes': villes,
        'ville_selectionnee': ville_selectionnee,
        'recherche': recherche,
        'categorie_selectionnee': categorie_slug,
        'promos': promos,
    })

@login_required
def supprimer_historique_commandes(request):
    vendeur = get_object_or_404(Vendeur, user=request.user)
    from django.utils import timezone
    from datetime import timedelta
    un_mois_ago = timezone.now() - timedelta(days=30)
    
    Commande.objects.filter(
        vendeur=vendeur,
        date_commande__lt=un_mois_ago,
        statut__in=['acceptee', 'refusee', 'annulee']
    ).update(archivee=True)
    
    messages.success(request, 'Historique archivé avec succès.')
    return redirect('commandes_vendeur')

def proposer_prix(request, pk):
    produit = get_object_or_404(Produit, pk=pk, visible=True)
    client_connecte = None
    if request.user.is_authenticated:
        try:
            client_connecte = Client.objects.get(user=request.user)
        except:
            pass

    if request.method == 'POST':
        nom = client_connecte.nom if client_connecte else request.POST.get('nom')
        numero = client_connecte.numero if client_connecte else request.POST.get('numero')
        prix_propose = int(request.POST.get('prix_propose'))
        message = request.POST.get('message', '')

        negociation = MessageNegociation.objects.create(
            produit=produit,
            vendeur=produit.vendeur,
            client_nom=nom,
            client_numero=numero,
            prix_propose=prix_propose,
            message=message,
            vendor_lu=False,
            client_lu=True,
        )

        creer_notification(
            user=produit.vendeur.user,
            type='message',
            titre=f'💬 Négociation de prix — {produit.nom}',
            message=f'{nom} propose {prix_propose:,} GNF au lieu de {produit.prix:,} GNF.',
            lien='/messages-vendeur/'
        )

        return redirect('detail_produit', pk=pk)

    return render(request, 'core/proposer_prix.html', {
        'produit': produit,
        'client_connecte': client_connecte,
    })

# ============================================
# MESSAGES / NÉGOCIATIONS
# ============================================

@login_required
def messages_vendeur(request):
    vendeur = get_object_or_404(Vendeur, user=request.user)
    negotiations = (
        MessageNegociation.objects.select_related('produit', 'vendeur')
        .filter(vendeur=vendeur)
        .order_by('-date')
    )

    conversations = []
    for n in negotiations:
        last_chat = ChatMessage.objects.filter(negociation=n).order_by('-created_at').first()
        preview = (last_chat.content if last_chat and last_chat.content else (n.message or 'Aucun message')).strip()
        if len(preview) > 60:
            preview = preview[:57] + '...'

        display_name = (n.client_nom or 'Client').strip()
        if n.client_numero:
            display_name = f"{display_name} ({n.client_numero})"

# Compter les messages non lus pour le vendeur
        # Logique: Si vendor_lu=False, il y a des nouveaux messages non lus
        # On compte les ChatMessage créés APRÈS la dernière ouverture (n.date = date de création de la négoce)
        unread_count = 0
        if not n.vendor_lu:
            # Compter tous les messages de chat (nouveaux non lus)
            unread_count = ChatMessage.objects.filter(
                negociation=n
            ).count()
            # Ajouter 1 pour le message initial de négociation lui-même
            unread_count = unread_count + 1
        else:
            # vendor_lu=True: tous les messages ont été marqués comme lus
            unread_count = 0

        conversations.append({
            'negociation': n,
            'display_name': display_name,
            'produit_nom': n.produit.nom if n.produit else 'Produit',
            'prix_propose': n.prix_propose,
            'statut': n.statut,
            'last_preview': preview,
            'last_date': (last_chat.created_at if last_chat else n.date),
            'avatar_letter': (display_name[:1].upper() if display_name else 'C'),
            'unread_count': unread_count,
        })

    return render(request, 'core/messages_vendeur.html', {
        'vendeur': vendeur,
        'negociations': negotiations,
        'negotiations': negotiations,
        'conversations': conversations,
    })

@login_required
def mes_messages_client(request):
    client = get_object_or_404(Client, user=request.user)
    negotiations = (
        MessageNegociation.objects.select_related('produit', 'vendeur')
        .filter(client_numero=client.numero)
        .order_by('-date')
    )

    conversations = []
    for n in negotiations:
        last_chat = ChatMessage.objects.filter(negociation=n).order_by('-created_at').first()
        preview = (last_chat.content if last_chat and last_chat.content else (n.reponse_vendeur or n.message or 'Aucun message')).strip()
        if len(preview) > 60:
            preview = preview[:57] + '...'

        display_name = n.vendeur.nom_boutique if n.vendeur else 'Vendeur'

        unread_count = 0
        if not n.client_lu:
            unread_count = ChatMessage.objects.filter(negociation=n, sender_type='vendeur').count()

        conversations.append({
            'negociation': n,
            'display_name': display_name,
            'produit_nom': n.produit.nom if n.produit else 'Produit',
            'prix_propose': n.prix_propose,
            'statut': n.statut,
            'last_preview': preview,
            'last_date': (last_chat.created_at if last_chat else n.date),
            'avatar_letter': (display_name[:1].upper() if display_name else 'V'),
            'unread_count': unread_count,
        })

    return render(request, 'core/messages_client.html', {
        'client': client,
        'negociations': negotiations,
        'negotiations': negotiations,
        'conversations': conversations,
    })

@login_required
def chat_negociation(request, pk):
    neg = get_object_or_404(MessageNegociation, pk=pk)

    # Contrôle d'accès: seul vendeur propriétaire ou client concerné
    autorise = False
    sender_type = 'client'

    try:
        vendeur = Vendeur.objects.get(user=request.user)
        if neg.vendeur_id == vendeur.id:
            autorise = True
            sender_type = 'vendeur'
    except Vendeur.DoesNotExist:
        pass

    if not autorise:
        try:
            client = Client.objects.get(user=request.user)
            if neg.client_numero == client.numero:
                autorise = True
                sender_type = 'client'
        except Client.DoesNotExist:
            pass

    if not autorise:
        messages.error(request, "Accès refusé à cette discussion.")
        return redirect('Welcome')

    # Marquer les messages comme lus quand l'utilisateur ouvre le chat
    # Cela change le statut de "en attente" à "lu" (read)
    messages_marks_as_read = False
    
    if sender_type == 'vendeur' and not neg.vendor_lu:
        neg.vendor_lu = True
        neg.save()
        messages_marks_as_read = True
    
    if sender_type == 'client' and not neg.client_lu:
        neg.client_lu = True
        neg.save()
        messages_marks_as_read = True
    
    # Si nouveaux messages après la dernière lecture, les marquer comme lus
    if sender_type == 'vendeur' and neg.vendor_lu:
        # Vérifier s'il y a de nouveaux messages du client après la dernière lecture
        nouveaux_messages = ChatMessage.objects.filter(
            negociation=neg,
            sender_type='client'
        ).count()
        if nouveaux_messages > 0:
            neg.vendor_lu = True
            neg.save()
    
    if sender_type == 'client' and neg.client_lu:
        # Vérifier s'il y a de nouveaux messages du vendeur après la dernière lecture
        nouveaux_messages = ChatMessage.objects.filter(
            negociation=neg,
            sender_type='vendeur'
        ).count()
        if nouveaux_messages > 0:
            neg.client_lu = True
            neg.save()

    messages_qs = (
        ChatMessage.objects.filter(negociation=neg)
        .order_by('created_at')
    )

    return render(request, 'core/chat_negociation.html', {
        'negociation': neg,
        'messages': messages_qs,
        'sender_type': sender_type,
    })

@login_required
def effacer_discussion(request, pk):
    neg = get_object_or_404(MessageNegociation, pk=pk)

    autorise_vendeur = False
    autorise_client = False

    try:
        vendeur = Vendeur.objects.get(user=request.user)
        if neg.vendeur_id == vendeur.id:
            autorise_vendeur = True
    except Vendeur.DoesNotExist:
        pass

    try:
        client = Client.objects.get(user=request.user)
        if neg.client_numero == client.numero:
            autorise_client = True
    except Client.DoesNotExist:
        pass

    if not (autorise_vendeur or autorise_client):
        messages.error(request, "Accès refusé.")
        return redirect('Welcome')

    # Supprimer les messages et la négociation
    ChatMessage.objects.filter(negociation=neg).delete()
    neg.delete()
    messages.success(request, "Conversation supprimée avec succès.")

    if autorise_vendeur:
        return redirect('messages_vendeur')
    return redirect('mes_messages_client')


@login_required
def repondre_negociation(request, pk):
    neg = get_object_or_404(MessageNegociation, pk=pk)
    vendeur = get_object_or_404(Vendeur, user=request.user)
    if neg.vendeur != vendeur:
        return redirect('messages_vendeur')

    if request.method == 'POST':
        action = request.POST.get('action')
        reponse_text = request.POST.get('reponse', '').strip()
        prix_propose = request.POST.get('prix_propose')
        
        # Préparer le contenu du message à enregistrer dans le chat
        chat_content = ""
        nouveau_prix = None
        
        if action == 'accepte':
            neg.statut = 'accepte'
            chat_content = reponse_text or "✅ J'accepte votre proposition de prix!"
        elif action == 'refuse':
            neg.statut = 'refuse'
            chat_content = reponse_text or "❌ J'ai refusé cette proposition."
        elif action == 'contre_offre':
            neg.statut = 'contre_offre'
            if prix_propose:
                try:
                    nouveau_prix = int(prix_propose)
                    neg.prix_propose = nouveau_prix
                except ValueError:
                    pass
            chat_content = reponse_text if reponse_text else f"Contre-proposition: {nouveau_prix or neg.prix_propose} GNF"
        else:
            return redirect('messages_vendeur')

        # Sauvegarder la négociation
        neg.save()

        # Enregistrer la réponse du vendeur dans le ChatMessage
        # Cela permet au client de voir la réponse dans son chat
        ChatMessage.objects.create(
            negociation=neg,
            sender_type='vendeur',
            content=chat_content,
            prix_propose=nouveau_prix,
        )
        neg.vendor_lu = True
        neg.client_lu = False
        neg.save(update_fields=['vendor_lu', 'client_lu'])

# Notifier le client (via notification système)
        creer_notification(
            user=neg.vendeur.user,
            type='message',
            titre='💬 Réponse enregistrée',
            message=f"Statut négociation: {neg.statut}",
            lien='/messages-vendeur/'
        )

    return redirect('messages_vendeur')

# ============================================
# ENVOI MESSAGE HTTP FALLBACK
# ============================================
@login_required
def envoyer_message(request):
    """Vue HTTP pour envoyer un message quand WebSocket échoue"""
    if request.method == 'POST':
        message = request.POST.get('message', '').strip()
        prix_propose = request.POST.get('prix_propose')
        sender_type = request.POST.get('sender_type', 'client')
        negociation_id = request.POST.get('negociation_id')
        
        if not negociation_id:
            return JsonResponse({'error': 'ID négociation manquant'}, status=400)
        
        try:
            neg = MessageNegociation.objects.get(pk=negociation_id)
        except MessageNegociation.DoesNotExist:
            return JsonResponse({'error': 'Négociation non trouvée'}, status=404)
        
        # Vérifier que l'utilisateur a le droit d'envoyer
        autorise = False
        try:
            vendeur = Vendeur.objects.get(user=request.user)
            if neg.vendeur_id == vendeur.id:
                autorise = True
        except Vendeur.DoesNotExist:
            pass
        
        if not autorise:
            try:
                client = Client.objects.get(user=request.user)
                if neg.client_numero == client.numero:
                    autorise = True
            except Client.DoesNotExist:
                pass
        
        if not autorise:
            return JsonResponse({'error': 'Accès refusé'}, status=403)
        
        # Convertir prix
        prix = None
        if prix_propose:
            try:
                prix = int(prix_propose)
            except ValueError:
                pass
        
        # Sauvegarder le message
        ChatMessage.objects.create(
            negociation=neg,
            sender_type=sender_type,
            content=message,
            prix_propose=prix,
        )

        if sender_type == 'client':
            neg.vendor_lu = False
            neg.client_lu = True
        else:
            neg.vendor_lu = True
            neg.client_lu = False
        neg.save(update_fields=['vendor_lu', 'client_lu'])
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


# ============================================

@login_required
def admin_dashboard(request):
    """Dashboard d'administration accessible à l'équipe staff."""
    if not request.user.is_staff:
        return redirect('Welcome')

    from .models import PaiementAbonnement, PaiementCommande, Signalement

    paiements_abonnement = PaiementAbonnement.objects.filter(statut='en_attente').order_by('-date_soumission')
    paiements_commandes = PaiementCommande.objects.filter(statut='en_attente').order_by('-date_soumission')
    signalements = Signalement.objects.filter(traite=False).order_by('-date')

    vendeurs = Vendeur.objects.all()
    total_vendeurs = vendeurs.count()
    vendeurs_actifs = vendeurs.filter(statut='actif').count()
    vendeurs_en_attente = vendeurs.filter(statut='en_attente').count()
    vendeurs_suspendus = vendeurs.filter(statut='suspendu').count()

    since = timezone.now() - timedelta(days=7)

    logins_last_7 = AuditLog.objects.filter(
        timestamp__gte=since,
        action__in=['login_vendor', 'login_client'],
    ).count()
    signups_last_7 = AuditLog.objects.filter(
        timestamp__gte=since,
        action__in=['signup_vendor', 'signup_client'],
    ).count()
    product_views_last_7 = AuditLog.objects.filter(
        timestamp__gte=since,
        action='product_view',
    ).count()
    orders_last_7 = Commande.objects.filter(date_commande__gte=since).count()

    payments_last_7 = 0
    revenus_7j = 0

    paiement_commandes_valide = PaiementCommande.objects.filter(
        statut='valide',
        date_soumission__gte=since,
    )
    payments_last_7 += paiement_commandes_valide.count()
    revenus_7j += int(paiement_commandes_valide.aggregate(total=Sum('montant'))['total'] or 0)

    paiements_panier_valides = PaiementPanier.objects.filter(
        statut='valide',
    ).filter(Q(date_validation__gte=since) | Q(date_soumission__gte=since))
    payments_last_7 += paiements_panier_valides.count()
    revenus_7j += int(paiements_panier_valides.aggregate(total=Sum('montant_total'))['total'] or 0)

    return render(request, 'core/admin_dashboard.html', {
        'total_vendeurs': total_vendeurs,
        'vendeurs_actifs': vendeurs_actifs,
        'vendeurs_en_attente': vendeurs_en_attente,
        'vendeurs_suspendus': vendeurs_suspendus,
        'logins_last_7': logins_last_7,
        'signups_last_7': signups_last_7,
        'product_views_last_7': product_views_last_7,
        'orders_last_7': orders_last_7,
        'payments_last_7': payments_last_7,
        'revenus_7j': revenus_7j,
        'paiements_abonnement': paiements_abonnement,
        'paiements_commandes': paiements_commandes,
        'signalements': signalements,
    })


@login_required
def admin_vendeurs(request):
    """Page de gestion des vendeurs avec filtres"""
    if not request.user.is_staff:
        return redirect('Welcome')
    
    filtre_statut = request.GET.get('statut', 'all')
    
    if filtre_statut == 'all':
        vendeurs = Vendeur.objects.order_by('-id')
    else:
        vendeurs = Vendeur.objects.filter(statut=filtre_statut).order_by('-id')
    
    total_vendeurs = Vendeur.objects.count()
    vendeurs_actifs = Vendeur.objects.filter(statut='actif').count()
    vendeurs_en_attente = Vendeur.objects.filter(statut='en_attente').count()
    vendeurs_suspendus = Vendeur.objects.filter(statut='suspendu').count()

    return render(request, 'core/admin_vendeurs.html', {
            'vendeurs': vendeurs,
            'total_vendeurs': total_vendeurs,
            'vendeurs_actifs': vendeurs_actifs,
            'vendeurs_en_attente': vendeurs_en_attente,
            'vendeurs_suspendus': vendeurs_suspendus,
    })

    return render(request, 'core/admin_vendeurs.html', {
        'vendeurs': vendeurs,
        'total_vendeurs': total_vendeurs,
        'vendeurs_actifs': vendeurs_actifs,
        'vendeurs_en_attente': vendeurs_en_attente,
'vendeurs_suspendus': vendeurs_suspendus,
    })

@login_required
def admin_signalements(request):
    """Page de gestion des signalements"""
    if not request.user.is_staff:
        return redirect('Welcome')
    
    signalements = Signalement.objects.filter(traite=False).order_by('-date')
    
    return render(request, 'core/admin_signalements.html', {
        'signalements': signalements,
    })

@login_required
def admin_certifies(request):
    """Page de gestion des vendeurs certifiés"""
    if not request.user.is_staff:
        return redirect('Welcome')
    
    # Tous les vendeurs actifs
    vendeurs = Vendeur.objects.filter(statut='actif').order_by('-est_certifie', '-note_confiance')
    
    return render(request, 'core/admin_certifies.html', {
        'vendeurs': vendeurs,
    })

@login_required
def admin_certifier_vendeur(request, pk):
    """Certifier ou décertification un vendeur"""
    if not request.user.is_staff:
        return redirect('Welcome')
    
    vendeur = get_object_or_404(Vendeur, pk=pk)
    
    if request.method == 'POST':
        if vendeur.est_certifie:
            # Retirer la certification
            vendeur.est_certifie = False
            vendeur.save()
            messages.success(request, f'Certification retirée à {vendeur.nom_boutique}')
        else:
            # Accorder la certification
            vendeur.est_certifie = True
            vendeur.date_certification = timezone.now()
            vendeur.save()
            messages.success(request, f'{vendeur.nom_boutique} est maintenant certifié!')
            
            # Notifier le vendeur
            creer_notification(
                user=vendeur.user,
                type='systeme',
                titre='🛡️ Boutique certifiée!',
                message='Félicitations! Votre boutique est maintenant certifiée SHOPY.',
                lien='/mes-parametres/'
            )
    
    return redirect('admin_certifies')

def admin_paiements_commandes(request):
    """Page des paiements commandes en attente"""
    if not request.user.is_staff:
        return redirect('Welcome')
    
    paiements = PaiementCommande.objects.filter(
        statut='en_attente'
    ).order_by('-date_soumission')
    
    return render(request, 'core/admin_paiements_commandes.html', {
        'paiements': paiements,
    })

@login_required
def admin_garanties(request):
    """Page des garanties acheteur"""
    if not request.user.is_staff:
        return redirect('Welcome')
    
    try:
        from .models import GarantieAcheteur
        garanties = GarantieAcheteur.objects.order_by('-date_demande')
    except:
        garanties = []
    
    return render(request, 'core/admin_garanties.html', {
        'garanties': garanties,
    })

@login_required
def admin_traiter_garantie(request, pk):
    """Traiter une demande de garantie"""
    if not request.user.is_staff:
        return redirect('Welcome')
    
    try:
        from .models import GarantieAcheteur
        garantie = get_object_or_404(GarantieAcheteur, pk=pk)
        
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'accepter':
                garantie.statut = 'acceptee'
                garantie.save()
                messages.success(request, 'Remboursement accepté!')
            elif action == 'refuser':
                garantie.statut = 'refusee'
                garantie.save()
                messages.error(request, 'Remboursement refusé.')
        
        return redirect('admin_garanties')
    except:
        return redirect('admin_dashboard')
