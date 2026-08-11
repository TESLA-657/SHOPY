"""
Module Notifications Push (FCM) & Email pour SHOPY.
Gère l'envoi des notifications via Firebase Cloud Messaging et Email SMTP.
"""

import os
import json
import requests
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string


# ============================================
# FIREBASE CLOUD MESSAGING (FCM)
# ============================================

def get_fcm_api_key():
    """Récupère la clé API FCM depuis les settings."""
    return getattr(settings, 'FCM_SERVER_KEY', None)


def send_push_notification(token_fcm, titre, message, data=None):
    """
    Envoie une notification push via FCM.
    
    Args:
        token_fcm: Token FCM de l'appareil
        titre: Titre de la notification
        message: Corps du message
        data: Données supplémentaires (dict)
    
    Returns:
        bool: True si succès
    """
    api_key = get_fcm_api_key()
    if not api_key:
        print("FCM: Pas de clé API configurée")
        return False
    
    payload = {
        'to': token_fcm,
        'notification': {
            'title': titre,
            'body': message,
            'icon': 'ic_notification',
            'color': '#007BFF',
        },
        'android': {
            'priority': 'high',
            'notification': {
                'channel_id': 'shopy_messages',
                'priority': 'high',
            }
        },
        'apns': {
            'payload': {
                'aps': {
                    'sound': 'default',
                    'badge': 1,
                }
            }
        }
    }
    
    if data:
        payload['data'] = data
    
    try:
        response = requests.post(
            'https://fcm.googleapis.com/fcm/send',
            json=payload,
            headers={
                'Authorization': f'key={api_key}',
                'Content-Type': 'application/json',
            },
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        print(f"FCM Error: {e}")
        return False


def send_push_to_user(user, titre, message, data=None):
    """
    Envoie une notification push à tous les appareils d'un utilisateur.
    """
    from .models import DeviceToken
    
    tokens = DeviceToken.objects.filter(user=user)
    for token in tokens:
        send_push_notification(token.fcm_token, titre, message, data)


def broadcast_notification(titre, message, data=None):
    """
    Envoie une notification à tous les utilisateurs.
    """
    from .models import DeviceToken
    
    tokens = DeviceToken.objects.values_list('fcm_token', flat=True).distinct()
    for token_fcm in tokens:
        if token_fcm:
            send_push_notification(token_fcm, titre, message, data)


# ============================================
# EMAIL SMTP
# ============================================

def send_email(to_email, subject, template_name, context=None, html=False):
    """
    Envoie un email via SMTP.
    
    Args:
        to_email: Adresse email du destinataire
        subject: Sujet de l'email
        template_name: Nom du template (sans extension)
        context: Contexte pour le template
        html: True pour HTML, False pour texte
    
    Returns:
        bool: True si succès
    """
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@shopy.com')
    
    if html:
        try:
            html_content = render_to_string(f'emails/{template_name}.html', context or {})
            return send_mail(
                subject=subject,
                message='',  # HTML only
                from_email=from_email,
                recipient_list=[to_email],
                html_message=html_content,
                fail_silently=False,
            )
        except Exception as e:
            print(f"Email HTML Error: {e}")
            return False
    else:
        try:
            text_content = render_to_string(f'emails/{template_name}.txt', context or {})
            return send_mail(
                subject=subject,
                message=text_content,
                from_email=from_email,
                recipient_list=[to_email],
                fail_silently=False,
            )
        except Exception as e:
            print(f"Email Text Error: {e}")
            return False


# Templates d'email courants
def email_nouvelle_commande(vendeur, commande):
    """Email quand une nouvelle commande est passée."""
    return send_email(
        to_email=vendeur.user.email,
        subject=f'🛒 Nouvelle commande #{commande.pk} - SHOPY',
        template_name='nouvelle_commande',
        context={
            'vendeur': vendeur,
            'commande': commande,
            'produit': commande.produit,
            'client': commande.nom_client,
        },
        html=True
    )


def email_paiement_recu(vendeur, paiement):
    """Email quand un paiement est reçu."""
    return send_email(
        to_email=vendeur.user.email,
        subject=f'💰 Paiement reçu - {paiement.montant:,} GNF',
        template_name='paiement_recu',
        context={
            'vendeur': vendeur,
            'paiement': paiement,
        },
        html=True
    )


def email_commande_acceptee(client, commande):
    """Email quand une commande est acceptée."""
    return send_email(
        to_email=client.user.email,
        subject=f'✅ Commande #{commande.pk} acceptée - SHOPY',
        template_name='commande_acceptee',
        context={
            'client': client,
            'commande': commande,
        },
        html=True
    )


def email_inscription_client(client):
    """Email de bienvenue pour nouveau client."""
    return send_email(
        to_email=client.user.email,
        subject='🎉 Bienvenue sur SHOPY Guinea!',
        template_name='bienvenue_client',
        context={'client': client},
        html=True
    )


def email_inscription_vendeur(vendeur):
    """Email de bienvenue pour nouveau vendeur."""
    return send_email(
        to_email=vendeur.user.email,
        subject='🏪 Votre boutique SHOPY est créée!',
        template_name='bienvenue_vendeur',
        context={'vendeur': vendeur},
        html=True
    )


# ============================================
# NOTIFICATION COMBINÉE (Push + Email)
# ============================================

def notifier_nouvelle_commande(vendeur, commande):
    """
    Notifie le vendeur d'une nouvelle commande (Push + Email).
    """
    # Push notification
    send_push_to_user(
        user=vendeur.user,
        titre=f'🛒 Nouvelle commande!',
        message=f'{commande.nom_client} a commandé {commande.produit.nom}',
        data={'type': 'commande', 'id': commande.pk}
    )
    
    # Email
    email_nouvelle_commande(vendeur, commande)


def notifier_paiement(client, paiement):
    """Notifie le client d'un paiement réussi."""
    send_push_to_user(
        user=client.user,
        titre='✅ Paiement réussi!',
        message=f'Votre paiement de {paiement.montant:,} GNF a été validé.',
        data={'type': 'paiement', 'id': paiement.pk}
    )


def notifier_message(vendeur, titre, message):
    """Notifie un vendeur d'un nouveau message."""
    send_push_to_user(
        user=vendeur.user,
        titre=titre,
        message=message,
        data={'type': 'message'}
    )
