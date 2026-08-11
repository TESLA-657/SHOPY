from django.conf import settings
from django.core.mail import send_mail

from .models import PaiementCommande, PaiementPanier

PAYMENT_METHOD_LABELS = {
    'orange_money': 'Orange Money',
    'mobile_money': 'Mobile Money',
    'carte_bancaire': 'Carte Bancaire',
    'paiement_livraison': 'Paiement à la livraison',
    'virement_bancaire': 'Virement bancaire',
}

OFFLINE_PAYMENT_METHODS = {
    'paiement_livraison',
    'virement_bancaire',
}


def get_payment_label(mode):
    return PAYMENT_METHOD_LABELS.get(mode, mode.replace('_', ' ').title())


def get_valid_payment_method(selected, allowed):
    if selected in allowed:
        return selected
    return allowed[0] if allowed else selected


def create_panier_payment(client, montant, mode, numero, reference):
    return PaiementPanier.objects.create(
        client=client,
        montant_total=montant,
        mode_paiement=mode,
        numero_paiement=numero or 'N/A',
        reference=reference or '',
    )


def create_commande_payment(commande, mode, numero, reference):
    return PaiementCommande.objects.create(
        commande=commande,
        mode_paiement=mode,
        numero_paiement=numero or 'N/A',
        montant=commande.prix_total,
        reference=reference or '',
    )


def notify_vendeur_payment_commande(commande, numero, reference, mode):
    try:
        subject = f'💰 Paiement reçu pour votre commande #{commande.pk}'
        body = f"""
Bonjour {commande.vendeur.nom_boutique},

Un paiement a été enregistré pour la commande #{commande.pk}.

=== INFOS COMMANDE ===
Produit : {commande.produit.nom}
Quantité : {commande.quantite}
Montant total : {commande.prix_total:,} GNF

=== INFOS CLIENT ===
Nom : {commande.nom_client}
Numéro client : {commande.numero_client}
Ville : {commande.ville_client}

=== PAIEMENT ===
Mode de paiement : {get_payment_label(mode)}
Identifiant / Numéro : {numero}
Référence : {reference or 'Non fournie'}

Connectez-vous à votre dashboard pour accepter ou refuser cette commande.
"""
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[commande.vendeur.user.email],
            fail_silently=True,
        )
    except Exception:
        pass
