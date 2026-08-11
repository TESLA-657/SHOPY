"""
Nouvelles Fonctionnalités SHOPY - Vues
Ce fichier contient les vues pour les fonctionnalités différenciantes:
4. Alertes Prix (Assistant IA)
5. Garantie Acheteur
6. Vendeurs Certifiés
7. Flash Sales
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta, datetime
from django.db.models import Count, Sum, Max
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from .models import (
    Vendeur, Client, Produit, Commande, GarantieAcheteur, 
    FlashSale, AlertePrix, EvaluationVendeur, Notification,
    MessageNegociation, PaiementCommande, PaiementPanier, Evaluation,
    Signalement, Favori, Abonnement
)
from .llm import generate_commercial_response


# ============================================================
# FONCTIONNALITÉS SHOPY - VENDEURS CERTIFIÉS (Fonctionnalité 6)
# ============================================================

@login_required
def vendeurs_certifies(request):
    """Liste des vendeurs certifiés avec leurs notes"""
    vendeures = Vendeur.objects.filter(
        est_certifie=True, 
        statut='actif'
    ).order_by('-note_confiance', '-nb_evaluations')
    
    # Pour chaque vendeur, récupérer les dernières évaluations
    evaluations_par_vendeur = {}
    for v in vendeures:
        evals = EvaluationVendeur.objects.filter(vendeur=v).order_by('-date')[:5]
        evaluations_par_vendeur[v.pk] = evals
    
    return render(request, 'core/vendeurs_certifies.html', {
        'vendeurs': vendeures,
        'evaluations_par_vendeur': evaluations_par_vendeur,
    })


@login_required
def demander_certification(request):
    """Demander la certification SHOPY pour un vendeur"""
    try:
        vendeur = Vendeur.objects.get(user=request.user)
    except Vendeur.DoesNotExist:
        messages.error(request, "Vous devez avoir un compte vendeur!")
        return redirect('Welcome')
    
    if request.method == 'POST':
        vendeur.demande_certification = True
        vendeur.date_demande_certification = timezone.now()
        vendeur.save()
        
        Notification.objects.create(
            user=vendeur.user,
            type='systeme',
            titre='📋 Demande de certification envoyée',
            message='Votre demande est en attente de validation.',
            lien='/mes-parametres/'
        )
        
        messages.success(request, "Votre demande de certification a été envoyée!")
        return redirect('dashboard_vendeur')
    
    return render(request, 'core/demander_certification.html', {
        'vendeur': vendeur,
    })


@login_required
def noter_vendeur(request, pk):
    """Noter un vendeur certifié"""
    try:
        vendeur = Vendeur.objects.get(pk=pk, est_certifie=True)
    except Vendeur.DoesNotExist:
        messages.error(request, "Vendeur non trouvé!")
        return redirect('vendeurs_certifies')
    
    try:
        client = Client.objects.get(user=request.user)
    except Client.DoesNotExist:
        messages.error(request, "Vous devez avoir un compte client!")
        return redirect('connexion_client')
    
    deja_note = EvaluationVendeur.objects.filter(
        vendeur=vendeur, 
        client_numero=client.numero
    ).exists()
    
    if request.method == 'POST':
        note = int(request.POST.get('note', 5))
        commentaire = request.POST.get('commentaire', '')
        
        if deja_note:
            eval_vendeur = EvaluationVendeur.objects.get(
                vendeur=vendeur, 
                client_numero=client.numero
            )
            eval_vendeur.note = note
            eval_vendeur.commentaire = commentaire
            eval_vendeur.save()
        else:
            EvaluationVendeur.objects.create(
                vendeur=vendeur,
                client_nom=client.nom,
                client_numero=client.numero,
                note=note,
                commentaire=commentaire,
            )
        
# Recalculer la note moyenne
        evals = EvaluationVendeur.objects.filter(vendeur=vendeur)
        if evals.count() > 0:
            nouvelle_note = sum(e.note for e in evals) / evals.count()
            vendeur.note_confiance = nouvelle_note
            vendeur.nb_evaluations = evals.count()
            vendeur.save()
        
        messages.success(request, "Merci pour votre évaluation!")
        return redirect('vendeurs_certifies')
    
    return render(request, 'core/noter_vendeur.html', {
        'vendeur': vendeur,
        'deja_note': deja_note,
    })


# ============================================================
# FONCTIONNALITÉS SHOPY - GARANTIE ACHETEUR (Fonctionnalité 5)
# ============================================================

@login_required
def mes_garanties(request):
    """Liste des garanties du client"""
    try:
        client = Client.objects.get(user=request.user)
    except Client.DoesNotExist:
        return redirect('Welcome')
    
    garanties = GarantieAcheteur.objects.filter(
        client_numero=client.numero
    ).order_by('-date_activation')
    
    return render(request, 'core/mes_garanties.html', {
        'garanties': garanties,
        'client': client,
    })


@login_required
def demander_remboursement(request, pk):
    """Demander un remboursement pour une garantie"""
    try:
        client = Client.objects.get(user=request.user)
    except Client.DoesNotExist:
        return redirect('Welcome')
    
    try:
        garantie = GarantieAcheteur.objects.get(pk=pk, client_numero=client.numero)
    except GarantieAcheteur.DoesNotExist:
        messages.error(request, "Garantie non trouvée!")
        return redirect('mes_garanties')
    
    if not garantie.est_active():
        messages.error(request, "Cette garantie n'est plus active!")
        return redirect('mes_garanties')
    
    if request.method == 'POST':
        motif = request.POST.get('motif', '')
        garantie.statut = 'utilisee'
        garantie.motif_refus = motif
        garantie.save()
        
        messages.success(request, "Votre demande de remboursement a été envoyée!")
        return redirect('mes_garanties')
    
    return render(request, 'core/demander_remboursement.html', {
        'garantie': garantie,
    })


@login_required
def admin_garanties(request):
    """Admin: gérer les demandes de remboursement"""
    if not request.user.is_staff:
        return redirect('Welcome')
    
    garanties = GarantieAcheteur.objects.filter(
        statut='utilisee'
    ).order_by('-date_activation')
    
    return render(request, 'core/admin_garanties.html', {
        'garanties': garanties,
    })


@login_required
def traiter_garantie(request, pk):
    """Admin: traiter une demande de garantie"""
    if not request.user.is_staff:
        return redirect('Welcome')
    
    garantie = get_object_or_404(GarantieAcheteur, pk=pk)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'accepter':
            garantie.montant_rembourse = garantie.montant_original
            messages.success(request, "Remboursement accordé!")
        else:
            garantie.statut = 'refusee'
            messages.info(request, "Demande refusée.")
        
        garantie.save()
    
    return redirect('admin_garanties')


# ============================================================
# FONCTIONNALITÉS SHOPY - FLASH SALES (Fonctionnalité 7)
# ============================================================

@login_required
def flash_sales(request):
    """Page des ventes flash"""
    flashsales = FlashSale.objects.filter(
        est_active=True,
        date_fin__gte=timezone.now()
    ).order_by('date_fin')
    
    return render(request, 'core/flash_sales.html', {
        'flashsales': flashsales,
    })


@login_required
def detail_flash_sale(request, pk):
    """Détail d'une vente flash"""
    flashsale = get_object_or_404(FlashSale, pk=pk, est_active=True)
    
    return render(request, 'core/detail_flash_sale.html', {
        'flashsale': flashsale,
    })


@login_required
def creer_flash_sale(request):
    """Créer une nouvelle vente flash"""
    try:
        vendeur = Vendeur.objects.get(user=request.user)
    except Vendeur.DoesNotExist:
        return redirect('Welcome')
    
    if vendeur.statut != 'actif':
        messages.error(request, "Votre boutique doit être active!")
        return redirect('dashboard_vendeur')
    
    produits = Produit.objects.filter(vendeur=vendeur, visible=True)
    
    if request.method == 'POST':
        produit_pk = request.POST.get('produit')
        prix_flash = int(request.POST.get('prix_flash'))
        quantite = int(request.POST.get('quantite', 1))
        heures = int(request.POST.get('duree', 1))
        
        try:
            produit = Produit.objects.get(pk=produit_pk, vendeur=vendeur)
        except Produit.DoesNotExist:
            messages.error(request, "Produit non trouvé!")
            return redirect('creer_flash_sale')
        
        prix_normal = int(produit.prix)
        if prix_flash >= prix_normal:
            messages.error(request, "Le prix flash doit être inférieur au prix normal!")
            return redirect('creer_flash_sale')
        
        date_fin = timezone.now() + timedelta(hours=heures)
        
        FlashSale.objects.create(
            produit=produit,
            prix_flash=prix_flash,
            quantite_disponible=quantite,
            date_fin=date_fin,
            cree_par=vendeur,
        )
        
        messages.success(request, "Flash Sale créé avec succès!")
        return redirect('dashboard_vendeur')
    
    return render(request, 'core/creer_flash_sale.html', {
        'produits': produits,
    })


@login_required
def acheter_flash_sale(request, pk):
    """Acheter un produit en flash sale"""
    flashsale = get_object_or_404(FlashSale, pk=pk)
    
    if not flashsale.est_en_cours():
        messages.error(request, "Cette vente flash est terminée!")
        return redirect('flash_sales')
    
    if flashsale.stock_restant() < 1:
        messages.error(request, "Stock épuisé!")
        return redirect('flash_sales')
    
    try:
        client = Client.objects.get(user=request.user)
    except Client.DoesNotExist:
        return redirect('connexion_client')
    
    if request.method == 'POST':
        quantite = int(request.POST.get('quantite', 1))
        
        if quantite > flashsale.stock_restant():
            messages.error(request, f"Stock insuffisant!")
            return redirect('acheter_flash_sale', pk=pk)
        
        commande = Commande.objects.create(
            produit=flashsale.produit,
            vendeur=flashsale.produit.vendeur,
            nom_client=client.nom,
            numero_client=client.numero,
            ville_client=client.ville,
            quantite=quantite,
            prix_unitaire=flashsale.prix_flash,
            prix_total=flashsale.prix_flash * quantite,
            statut='en_attente',
        )
        
        flashsale.quantite_vendue += quantite
        if flashsale.stock_restant() < 1:
            flashsale.est_active = False
        flashsale.save()
        
        return redirect('payer_commande', pk=commande.pk)
    
    return render(request, 'core/acheter_flash_sale.html', {
        'flashsale': flashsale,
    })


@login_required
def api_flash_sales(request):
    """API pour les flash sales (JSON pour countdown)"""
    flashsales = FlashSale.objects.filter(
        est_active=True,
        date_fin__gte=timezone.now()
    )
    
    data = []
    for fs in flashsales:
        delta = fs.date_fin - timezone.now()
        data.append({
            'id': fs.pk,
            'produit': fs.produit.nom,
            'prix_flash': fs.prix_flash,
            'stock': fs.stock_restant(),
            'temps_restant': fs.temps_restant(),
            'secondes': int(delta.total_seconds()) if delta.total_seconds() > 0 else 0,
        })
    
    return JsonResponse({'flashsales': data})


# ============================================================
# FONCTIONNALITÉS SHOPY - ALERTES PRIX (Fonctionnalité 4)
# ============================================================

@login_required
def alertes_prix(request):
    """Liste des alertes prix du client"""
    try:
        client = Client.objects.get(user=request.user)
    except Client.DoesNotExist:
        return redirect('Welcome')
    
    alertes = AlertePrix.objects.filter(
        client=client
    ).order_by('-date_creation')
    
    return render(request, 'core/alertes_prix.html', {
        'alertes': alertes,
    })


@login_required
def creer_alerte(request):
    """Créer une alerte prix"""
    try:
        client = Client.objects.get(user=request.user)
    except Client.DoesNotExist:
        return redirect('Welcome')
    
    if request.method == 'POST':
        produit_nom = request.POST.get('produit_nom')
        marque = request.POST.get('marque', '')
        prix_cible = int(request.POST.get('prix_cible'))
        ville = request.POST.get('ville', '')
        
        AlertePrix.objects.create(
            client=client,
            produit_nom=produit_nom,
            marque=marque,
            prix_cible=prix_cible,
            ville=ville,
        )
        
        messages.success(request, "Alerte créée!")
        return redirect('alertes_prix')
    
    return render(request, 'core/creer_alerte.html', {})


@login_required
def supprimer_alerte(request, pk):
    """Supprimer une alerte prix"""
    try:
        client = Client.objects.get(user=request.user)
    except Client.DoesNotExist:
        return redirect('Welcome')
    try:
        alerte = AlertePrix.objects.get(pk=pk, client=client)
        alerte.delete()
        messages.success(request, "Alerte supprimée!")
    except AlertePrix.DoesNotExist:
        pass
    
    return redirect('alertes_prix')


# ============================================================
# FONCTIONNALITÉS SHOPY - ASSISTANT IA POUR VENDEURS (Fonctionnalité 4)
# ============================================================

@ensure_csrf_cookie
@login_required
def assistant_ia_vendeur(request):
    """Assistant IA: Voir les alertes prix qui correspondent aux produits du vendeur"""
    try:
        vendeur = Vendeur.objects.get(user=request.user)
    except Vendeur.DoesNotExist:
        messages.error(request, "Vous devez avoir un compte vendeur!")
        return redirect('Welcome')
    
    # Récupérer les produits du vendeur
    produits_vendeur = Produit.objects.filter(vendeur=vendeur, visible=True)
    produits_noms = [p.nom.lower() for p in produits_vendeur]
    produits_marques = [p.marque.lower() if p.marque else '' for p in produits_vendeur]
    
    # Trouver toutes les alertes qui correspondent aux produits du vendeur
    alertes_correspondantes = []
    for alerte in AlertePrix.objects.all().order_by('-date_creation')[:50]:
        alerte_nom = alerte.produit_nom.lower() if alerte.produit_nom else ''
        alerte_marque = alerte.marque.lower() if alerte.marque else ''
        
        # Vérifier si l'alerte correspond à un produit du vendeur
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
            alertes_correspondantes.append(alerte)
    
    # Compter le total des alertes potentiellement interessantes
    total_alertes = len(alertes_correspondantes)
    
    return render(request, 'core/assistant_ia_vendeur.html', {
        'alertes': alertes_correspondantes,
        'total_alertes': total_alertes,
        'vendeur': vendeur,
    })


# ============================================================
# ADMIN - GESTION CERTIFICATION (depuis admin_dashboard)
# ============================================================

@login_required
def admin_certifier_vendeur(request, pk):
    """Admin: Certifier ou retirer certification d'un vendeur"""
    if not request.user.is_staff:
        return redirect('Welcome')
    
    vendeur = get_object_or_404(Vendeur, pk=pk)
    
    if request.method == 'POST':
        action = request.POST.get('action', 'certifier')
        
        if action == 'certifier':
            vendeur.est_certifie = True
            vendeur.date_certification = timezone.now()
            messages.success(request, f"{vendeur.nom_boutique} est maintenant certifiée!")
        else:  # retirer
            vendeur.est_certifie = False
            messages.info(request, f"Certification retirée à {vendeur.nom_boutique}")
        
        vendeur.save()
    
    return redirect('admin_dashboard')


# ============================================================
# FONCTIONNALITÉS SHOPY - ASSISTANT IA CONVERSATIONNEL (Fonctionnalité 4)
# ============================================================
@login_required
def assistant_ia_chat(request):
    """Assistant IA conversationnel pour les vendeurs - Répond aux questions en temps réel"""
    from django.db.models import Count, Sum, Max
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        vendeur = Vendeur.objects.get(user=request.user)
    except Vendeur.DoesNotExist:
        logger.error(f"Vendeur not found for user: {request.user}")
        return JsonResponse({'error': 'Vous devez avoir un compte vendeur!'}, status=403)
    except Exception as e:
        logger.error(f"Error getting vendeur: {e}")
        return JsonResponse({'error': str(e)}, status=500)
    
    if request.method == 'POST':
        raw_question = request.POST.get('question', '')
        question = (raw_question or '').strip().lower()

        # Try LLM for high-value, analytical or commercial requests
        llm_keywords = ['conseil', 'conseils', 'insight', 'insights', 'prévision', 'prévisions', 'projection', 'résumé', 'analyse', 'analyser', 'recommand', 'recommend', 'commercial']
        if any(k in question for k in llm_keywords):
            try:
                # Build a lightweight seller context to send to the LLM
                produits = Produit.objects.filter(vendeur=vendeur, visible=True)
                total_produits = produits.count()
                total_stock = sum(p.quantite for p in produits)
                commandes_30j = Commande.objects.filter(vendeur=vendeur, statut='acceptee', date_commande__gte=timezone.now() - timedelta(days=30))
                ventes_30j = int(commandes_30j.aggregate(total=Sum('prix_total'))['total'] or 0)

                vendeur_context = {
                    'nom_boutique': vendeur.nom_boutique,
                    'total_produits': total_produits,
                    'total_stock': total_stock,
                    'ventes_30j': ventes_30j,
                }

                # send the original text (preserve casing and punctuation) to the LLM
                llm_resp = generate_commercial_response(vendeur_context, raw_question or question)
                if llm_resp:
                    return JsonResponse({
                        'reponse': llm_resp,
                        'réponse': llm_resp,
                        'type': 'llm',
                        'vendeur': vendeur.nom_boutique,
                    })
            except Exception as e:
                # Fall back to rule-based response on error
                import logging
                logging.getLogger(__name__).exception('LLM routing failed')

        if not question:
            return JsonResponse({'réponse': 'Posez-moi une question sur votre boutique!'})
        
        # === ANALYSE DE LA QUESTION ET GÉNÉRATION DE LA RÉPONSE ===
        réponse = ""
        type_info = "général"
        
        # === STOCK & PRODUITS ===
        if any(mot in question for mot in ['stock', 'épuisé', 'rupture', 'quantité', 'quand']):
            produits = Produit.objects.filter(vendeur=vendeur, visible=True).order_by('quantite')
            faible_stock = [p for p in produits if p.quantite <= 3]
            
            if faible_stock:
                réponse = "📦 Produits avec peu de stock:\n"
                for p in faible_stock[:5]:
                    réponse += f"• {p.nom}: {p.quantite} unités\n"
                réponse += f"\n<i>Commandez bientôt pour ne pas manquer!</i>"
            else:
                réponse = "✅ Tous vos produits sont bien garnis!\n"
                total_stock = sum(p.quantite for p in produits)
                réponse += f"Vous avez {total_stock} unités en tout."
            type_info = "stock"
            
        elif any(mot in question for mot in ['produit', 'articles', 'catalogue', 'offre']):
            produits = Produit.objects.filter(vendeur=vendeur, visible=True)
            total_produits = produits.count()
            
            # Produits les plus chers et les moins chers
            plus_cher = produits.order_by('-prix').first()
            moins_cher = produits.order_by('prix').first()
            
            réponse = f"📦 Votre catalogue:\n"
            réponse += f"• {total_produits} produits en vente\n"
            if plus_cher:
                réponse += f"• Plus cher: {plus_cher.nom} à {int(plus_cher.prix):,} GNF\n"
            if moins_cher:
                réponse += f"• Moins cher: {moins_cher.nom} à {int(moins_cher.prix):,} GNF"
            type_info = "produits"
            
        # === COMMANDES & VENTES ===
        elif any(mot in question for mot in ['commande', 'commande', 'achats', 'acheté']):
            commandes = Commande.objects.filter(vendeur=vendeur)
            en_attente = commandes.filter(statut='en_attente').count()
            acceptees = commandes.filter(statut='acceptee').count()
            refusees = commandes.filter(statut='refusee').count()
            
            réponse = f"📋 État des commandes:\n"
            réponse += f"• En attente: {en_attente}\n"
            réponse += f"• Acceptées: {acceptees}\n"
            réponse += f"• Refusées: {refusees}\n"
            
            # Dernière commande
            dernier = commandes.order_by('-date_commande').first()
            if dernier:
                from django.utils.timesince import timesince
                réponse += f"\n📌 Dernière commande: {dernier.produit.nom} par {dernier.nom_client}"
            type_info = "commandes"
            
        elif any(mot in question for mot in ['vente', 'vendu', 'gain', 'revenu', 'argent', 'mois']):
            from datetime import datetime
            
            # Ventes du mois
            maintenant = timezone.now()
            debut_mois = maintenant.replace(day=1, hour=0, minute=0, second=0)
            
            # Si on est ler du mois, prendre le mois précédent
            if maintenant.month == 1:
                debut_mois = debut_mois.replace(year=maintenant.year-1, month=12)
            else:
                debut_mois = debut_mois.replace(year=maintenant.year, month=maintenant.month-1)
            
            commandes_mois = Commande.objects.filter(
                vendeur=vendeur,
                statut='acceptee',
                date_commande__gte=debut_mois
            )
            
            ventes_mois = commandes_mois.aggregate(total=Sum('prix_total'))['total'] or 0
            nb_ventes = commandes_mois.count()
            
            # Évolution vs mois dernier
            if maintenant.month == 1:
                debut_mois_dernier = debut_mois.replace(year=maintenant.year-1, month=11)
            else:
                debut_mois_dernier = debut_mois.replace(year=maintenant.year, month=maintenant.month-2)
            
            commandes_mois_dernier = Commande.objects.filter(
                vendeur=vendeur,
                statut='acceptee',
                date_commande__gte=debut_mois_dernier,
                date_commande__lt=debut_mois
            )
            ventes_mois_dernier = commandes_mois_dernier.aggregate(total=Sum('prix_total'))['total'] or 0
            
            évolution = ""
            if ventes_mois_dernier > 0:
                pct = ((ventes_mois - ventes_mois_dernier) / ventes_mois_dernier) * 100
                if pct > 0:
                    évolution = f"📈 +{int(pct)}% vs mois dernier"
                else:
                    évolution = f"📉 {int(pct)}% vs mois dernier"
            
            réponse = f"💰 Ventes ce mois:\n"
            réponse += f"• {int(ventes_mois):,} GNF\n"
            réponse += f"• {nb_ventes} commandes\n"
            if évolution:
                réponse += f"\n{évolution}"
            type_info = "ventes"
            
        # === PRODUIT LE PLUS COMMANDÉ ===
        elif any(mot in question for mot in ['plus commandé', 'plus populaire', 'meilleur', 'favori', 'demande']):
            produit_plus_cmd = Commande.objects.filter(
                vendeur=vendeur,
                statut='acceptee'
            ).values(
                'produit__nom'
            ).annotate(
                nb_ventes=Count('id')
            ).order_by('-nb_ventes').first()
            
            if produit_plus_cmd:
                réponse = f"🏆 Produit le plus commandé:\n"
                réponse += f"• {produit_plus_cmd['produit__nom']}\n"
                réponse += f"• {produit_plus_cmd['nb_ventes']} ventes"
            else:
                réponse = "📭 Pas encore de commandes acceptées.\n"
                réponse += "Continuez à promouvoir vos produits!"
            type_info = "stats"
            
        # === ABONNEMENT & STATUT ===
        elif any(mot in question for mot in ['abonnement', 'plan', 'premium', 'pro']):
            try:
                abo = getattr(vendeur, 'abonnement', None)
                if not abo:
                    raise AttributeError("No abonnement")
                réponse = f"🎫 Abonnement:\n"
                réponse += f"• Plan: {abo.plan.nom}\n"
                réponse += f"• Statut: {abo.statut}\n"
                réponse += f"• Limite produits: {abo.plan.limite_produits}"
                if abo.date_fin:
                    restant = abo.jours_restants()
                    réponse += f"\n• Jours restants: {restant}"
            except:
                réponse = "❓ Pas d'abonnement trouvé.\n"
                réponse += "Contactez l'administrateur."
            type_info = "abonnement"
            
        # === MESSAGES & NÉGOCIATIONS ===
        elif any(mot in question for mot in ['message', 'négociation', 'réponse', 'discution']):
            negotiations = MessageNegociation.objects.filter(vendeur=vendeur)
            non_lus = negotiations.filter(vendor_lu=False).count()
            
            réponse = f"💬 Messages:\n"
            réponse += f"• Non lus: {non_lus}\n"
            réponse += f"• Total: {negotiations.count()}"
            type_info = "messages"
            
        # === CLIENTS & ÉVALUATIONS ===
        elif any(mot in question for mot in ['note', 'avis', 'évaluation', 'confiance']):
            if getattr(vendeur, 'est_certifie', False):
                réponse = f"⭐ Votre boutique:\n"
                réponse += f"• Note de confiance: {vendeur.note_confiance}/5\n"
                réponse += f"• Nombre d'évaluations: {vendeur.nb_evaluations}\n"
                réponse += f"• Statut: Certifié ✅"
            else:
                réponse = "⭐ Votre boutique:\n"
                réponse += "Vous n'avez pas encore de certifié.\n"
                réponse += "Demandez la certification pour plus de visibilité!"
            type_info = "évaluation"
            
        # === RÉSUMÉ GÉNÉRAL ===
        elif any(mot in question for mot in ['résumé', 'summary', 'totale', 'tout']):
            produits = Produit.objects.filter(vendeur=vendeur, visible=True)
            commandes = Commande.objects.filter(vendeur=vendeur)
            total_stock = sum(p.quantite for p in produits)
            
            réponse = f"📊 Résumé de {vendeur.nom_boutique}:\n\n"
            réponse += f"📦 Produits: {produits.count()} en vente\n"
            réponse += f"📦 Stock total: {total_stock} unités\n"
            réponse += f"📋 Commandes: {commandes.count()} total\n"
            réponse += f"💰 Ventes mois: {int(vendeur.ventes_du_mois):,} GNF"
            type_info = "résumé"
            
        # === FLASH SALES ===
        elif any(mot in question for mot in ['flash', 'promotion', 'vente flash', 'deal']):
            flashsales = FlashSale.objects.filter(
                cree_par=vendeur,
                est_active=True,
                date_fin__gte=timezone.now()
            )
            if flashsales:
                réponse = f"⚡ Vos Flash Sales:\n"
                for fs in flashsales[:3]:
                    réponse += f"• {fs.produit.nom}: {int(fs.prix_flash):,} GNF\n"
                    réponse += f"  Stock: {fs.stock_restant()} / {fs.quantite_disponible}\n"
            else:
                réponse = "⚡ Pas de Flash Sales actif.\n"
                réponse += "Créez une promotion pour booster vos ventes!"
            type_info = "flash_sales"

        # === NOTIFICATIONS ===
        elif any(mot in question for mot in ['notification', 'alerte', 'nouveau', 'recent']):
            notifications = Notification.objects.filter(
                user=vendeur.user
            ).order_by('-date')[:5]
            nb_non_lues = notifications.filter(lu=False).count()
            
            réponse = f"🔔 Notifications:\n"
            réponse += f"• Non lues: {nb_non_lues}\n"
            réponse += f"• Total: {notifications.count()}"
            type_info = "notifications"

        # === GARANTIES ACHETEUR ===
        elif any(mot in question for mot in ['garantie', 'remboursement', 'acheteur']):
            garanties = GarantieAcheteur.objects.filter(
                commande__vendeur=vendeur
            )
            actives = garanties.filter(statut='active').count()
            utilisees = garanties.filter(statut='utilisee').count()
            
            réponse = f"🛡️ Garanties Acheteur:\n"
            réponse += f"• Actives: {actives}\n"
            réponse += f"• Utilisées: {utilisees}"
            type_info = "garanties"

        # === STATUT BOUTIQUE ===
        elif any(mot in question for mot in ['statut', 'état', 'active', 'boutique']):
            réponse = f"🏪 Statut de {vendeur.nom_boutique}:\n"
            réponse += f"• Statut: {vendeur.statut}\n"
            if vendeur.statut == 'actif':
                réponse += "• ✅ Votre boutique est active\n"
                réponse += f"• Vendeur vérifié: {'Oui ⭐' if vendeur.est_certifie else 'Non'}"
            else:
                réponse += "• ⚠️ Votre boutique n'est pas encore active"
            type_info = "statut"

        # === COMPARAISON SEMAINES (NOUVEAU) ===
        elif any(mot in question for mot in ['semaine vs', 'cette semaine', 'comparaison semaine', 'semaine dernière', 'vs semaine']):
            maintenant = timezone.now()
            debut_semaine_act = maintenant - timedelta(days=maintenant.weekday())
            debut_semaine_act = debut_semaine_act.replace(hour=0, minute=0, second=0)
            debut_semaine_prec = debut_semaine_act - timedelta(days=7)
            
            cmd_semaine_act = Commande.objects.filter(vendeur=vendeur, statut='acceptee', date_commande__gte=debut_semaine_act)
            nb_semaine_act = cmd_semaine_act.count()
            rev_semaine_act = cmd_semaine_act.aggregate(total=Sum('prix_total'))['total'] or 0
            
            cmd_semaine_prec = Commande.objects.filter(vendeur=vendeur, statut='acceptee', date_commande__gte=debut_semaine_prec, date_commande__lt=debut_semaine_act)
            nb_semaine_prec = cmd_semaine_prec.count()
            rev_semaine_prec = cmd_semaine_prec.aggregate(total=Sum('prix_total'))['total'] or 0
            
            evolution = ""
            if nb_semaine_prec > 0:
                pct = ((nb_semaine_act - nb_semaine_prec) / nb_semaine_prec) * 100
                if pct > 0:
                    evolution = f"+{int(pct)}% vs semaine dernière"
                elif pct < 0:
                    evolution = f"{int(pct)}% vs semaine dernière"
                else:
                    evolution = "Stable vs semaine dernière"
            
            réponse = f"Cette semaine vs semaine dernière:\nCette semaine: {nb_semaine_act} cmd • {int(rev_semaine_act):,} GNF\nSemaine dernière: {nb_semaine_prec} cmd • {int(rev_semaine_prec):,} GNF\n{evolution}"
            type_info = "comparaison"


# === INSIGHTS ET RECOMMANDATIONS (NOUVEAU) ===
        elif any(mot in question for mot in ['conseil', 'conseils', 'suggestion', 'améliorer', 'advice', 'tips', 'recommander']):
            insights = []
            
            produits = Produit.objects.filter(vendeur=vendeur, visible=True)
            faible_stock = [p for p in produits if p.quantite <= 3]
            if faible_stock:
                insights.append(f"{len(faible_stock)} produit(s) avec peu de stock")
            
            commande_recente = Commande.objects.filter(vendeur=vendeur, date_commande__gte=timezone.now() - timedelta(days=7)).count()
            if commande_recente == 0:
                insights.append("Aucune commande cette semaine")
            
            negotiations = MessageNegociation.objects.filter(vendeur=vendeur, vendor_lu=False).count()
            if negotiations > 0:
                insights.append(f"{negotiations} message(s) non lu(s)")
            
            if getattr(vendeur, 'est_certifie', False) and getattr(vendeur, 'note_confiance', 0) < 4:
                insights.append("Note à améliorer")
            
            refusees = Commande.objects.filter(vendeur=vendeur, statut='refusee').count()
            total_cmd = Commande.objects.filter(vendeur=vendeur).count()
            if total_cmd > 0 and (refusees / total_cmd) > 0.3:
                insights.append("Taux de refus élevé")
            
            if insights:
                réponse = "Insights:\n" + "\n".join(insights)
            else:
                réponse = "Tout va bien!"
            type_info = "insights"


        # === PRÉVISIONS ET TENDANCES (NOUVEAU) ===
        elif any(mot in question for mot in ['prévisions', 'prévision', 'projection', 'forecast', 'predict', 'future']):
            maintenant = timezone.now()
            jour_prec = maintenant - timedelta(days=14)
            
            daily_sales = []
            for i in range(14):
                jour = jour_prec + timedelta(days=i)
                cmd_jour = Commande.objects.filter(vendeur=vendeur, statut='acceptee', date_commande__date=jour.date())
                total_jour = cmd_jour.aggregate(total=Sum('prix_total'))['total'] or 0
                daily_sales.append(total_jour)
            
            if len(daily_sales) >= 7:
                moyenne = sum(daily_sales[-7:]) / 7
            else:
                moyenne = sum(daily_sales) / len(daily_sales) if daily_sales else 0
            
            if len(daily_sales) >= 7:
                premiere_semaine = sum(daily_sales[:7])
                deuxieme_semaine = sum(daily_sales[7:])
                if deuxieme_semaine > premiere_semaine * 1.1:
                    tendance = "Haussiere"
                elif deuxieme_semaine < premiere_semaine * 0.9:
                    tendance = "Baissiere"
                else:
                    tendance = "Stable"
            else:
                tendance = "Donnees insuffisantes"
            
            projection = moyenne * 7
            
            réponse = f"Previsions:\nMoyenne mobile: {int(moyenne):,} GNF/jour\nTendance: {tendance}\nProjection 7 jours: {int(projection):,} GNF"
            type_info = "prévisions"


# === REVENUS TOTAUX ===
        elif any(mot in question for mot in ['revenu total', 'profit', 'chiffre affaires', 'revenus', 'revenu']):
            commandes_validees = Commande.objects.filter(vendeur=vendeur, statut='acceptee')
            revenu_total = commandes_validees.aggregate(total=Sum('prix_total'))['total'] or 0
            nb_commandes = commandes_validees.count()
            revenu_moyen = int(revenu_total / nb_commandes) if nb_commandes > 0 else 0
            réponse = f"💵 Revenus:\n• Total: {int(revenu_total):,} GNF\n• Commandes: {nb_commandes}\n• Moyenne: {revenu_moyen:,} GNF"
            type_info = "revenus"

        # === LOCALISATION CLIENTS ===
        elif any(mot in question for mot in ['ville', 'localisation', 'region', 'ou sont']):
            commandes = Commande.objects.filter(vendeur=vendeur, statut='acceptee').values('ville_client').annotate(nb_cmd=Count('id')).order_by('-nb_cmd')[:5]
            réponse = f"📍 Clients par ville:\n"
            has_data = False
            for cmd in commandes:
                if cmd['ville_client']:
                    réponse += f"• {cmd['ville_client']}: {cmd['nb_cmd']} cmd\n"
                    has_data = True
            if not has_data:
                réponse += "Pas encore de données"
            type_info = "localisation"

        # === MEILLEURS CLIENTS ===
        elif any(mot in question for mot in ['meilleur client', 'top client', 'fidel', 'frequent']):
            meilleurs = Commande.objects.filter(vendeur=vendeur, statut='acceptee').values('nom_client').annotate(nb_achats=Count('id'), total_dep=Sum('prix_total')).order_by('-total_dep')[:5]
            réponse = f"👑 Meilleurs clients:\n"
            has_data = False
            for i, c in enumerate(meilleurs, 1):
                réponse += f"{i}. {c['nom_client']}: {c['nb_achats']} achats\n"
                has_data = True
            if not has_data:
                réponse += "Pas encore de clients"
            type_info = "clients"

        # === TENDANCES VENTES ===
        elif any(mot in question for mot in ['tendances', "aujourd'hui", 'cette semaine', 'quotidien']):
            aujourd = timezone.now().date()
            cmd_today = Commande.objects.filter(vendeur=vendeur, statut='acceptee', date_commande__date=aujourd)
            nb_today = cmd_today.count()
            rev_today = cmd_today.aggregate(total=Sum('prix_total'))['total'] or 0
            
            # Cette semaine
            debut_semaine = timezone.now() - timedelta(days=timezone.now().weekday())
            cmd_semaine = Commande.objects.filter(vendeur=vendeur, statut='acceptee', date_commande__gte=debut_semaine)
            nb_semaine = cmd_semaine.count()
            rev_semaine = cmd_semaine.aggregate(total=Sum('prix_total'))['total'] or 0
            
            réponse = f"📈 Tendances:\n🕐 Aujourd'hui: {nb_today} cmd • {int(rev_today):,} GNF\n📅 Cette semaine: {nb_semaine} cmd • {int(rev_semaine):,} GNF"
            type_info = "tendances"

        # === PRIX & PROMOTIONS ===
        elif any(mot in question for mot in ['promotion', 'prix', 'promo', 'reduire prix']):
            produits = Produit.objects.filter(vendeur=vendeur, visible=True)
            
            # Check for any products with promo pricing
            avec_promo = []
            for p in produits:
                if hasattr(p, 'prix_promo') and p.prix_promo and p.prix_promo < p.prix:
                    avec_promo.append(p)
            
            réponse = f"🏷️ Prix produits:\n• Total: {produits.count()} produits\n• En promo: {len(avec_promo)}"
            
            if avec_promo:
                réponse += "\n💥 Promotions:\n"
                for p in avec_promo[:3]:
                    reduction = int((p.prix - p.prix_promo) / p.prix * 100) if p.prix > 0 else 0
                    réponse += f"• {p.nom}: -{reduction}% ({int(p.prix_promo):,} GNF)\n"
            
            type_info = "promotions"


        # === AIDE ===
        elif any(mot in question for mot in ['aide', 'help', 'comment', 'faq']):
            réponse = "💡 Aide - Questions fréquentes:\n\n"
            réponse += "📦 Produits:\n"
            réponse += "• Quels produits sont en rupture de stock?\n"
            réponse += "• Liste tous mes produits\n\n"
            réponse += "💰 Ventes:\n"
            réponse += "• Combien de ventes ce mois?\n"
            réponse += "• Quel produit est le plus vendu?\n\n"
            réponse += "📋 Commandes:\n"
            réponse += "• Commandes en attente?\n"
            réponse += "• Dernière commande?\n\n"
            réponse += "🎫 Autre:\n"
            réponse += "• Mon abonnement?\n"
            réponse += "• Mes messages?"
            type_info = "aide"

        # === QUESTION NON COMPRISE ===
        else:
            réponse = "🤔 Je n'ai pas bien compris.\n\n"
            réponse += "Essayez ces questions:\n"
            réponse += "• Quels produits sont en rupture de stock ?\n"
            réponse += "• Quel est mon produit le plus commandé ?\n"
            réponse += "• Combien de ventes ce mois ?\n"
            réponse += "• Ai-je des commandes en attente ?\n"
            réponse += "• Quel est mon abonnement ?\n"
            réponse += "• Combien de messages non lus ?\n"
            réponse += "• Affiche mes flash sales\n"
            réponse += "• Quel est le statut de ma boutique?"
        
# Retourner la réponse avec les deux clés pour compatibilité
        return JsonResponse({
            'reponse': réponse,  # Sans accent pour éviter les problèmes d'encodage
            'réponse': réponse,  # Avec accent pour compatibilité
            'type': type_info,
            'vendeur': vendeur.nom_boutique,
        })

    # GET request - return chat page
    return render(request, 'core/assistant_ia_chat.html', {
        'vendeur': vendeur,
    })
