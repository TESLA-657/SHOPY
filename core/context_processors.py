import json
from django.core.serializers.json import DjangoJSONEncoder

from .models import Notification, Annonce

def notifications_count(request):
    if request.user.is_authenticated:
        # Exclure les notifications de type 'message' (négociations de prix) et 'securite' (signalements) des toasts
        # Elles apparaîtront uniquement dans la page Notifications
        unread_qs = Notification.objects.filter(
            user=request.user, 
            lue=False
        ).exclude(type='message').exclude(type='securite').order_by('-date')[:4]
        
        nb = Notification.objects.filter(user=request.user, lue=False).count()
        
        type_map = {
            'commande': 'success',
            'abonnement': 'success',
            'message': 'info',
            'securite': 'error',
            'systeme': 'info',
        }
        notifications = [
            {
                'title': notif.titre,
                'body': notif.message,
                'type': type_map.get(notif.type, 'info'),
                'link': notif.lien,
            }
            for notif in unread_qs
        ]
        try:
            is_vendeur = hasattr(request.user, 'vendeur') and request.user.vendeur is not None
        except Exception:
            is_vendeur = False

        try:
            is_client = hasattr(request.user, 'client') and request.user.client is not None
        except Exception:
            is_client = False

        active_url = request.resolver_match.url_name if hasattr(request, 'resolver_match') and request.resolver_match else ''

        # Annonces actives pour la barre d'info (spam fermable)
        annonces_vendeur = []
        annonces_client = []
        try:
            if is_vendeur:
                annonces_vendeur = [
                    ann for ann in
                    Annonce.objects.filter(cible__in=['vendeur', 'tous']).filter(actif=True)
                    if ann.est_active()
                ][:3]
            elif is_client:
                annonces_client = [
                    ann for ann in
                    Annonce.objects.filter(cible__in=['client', 'tous']).filter(actif=True)
                    if ann.est_active()
                ][:3]
        except Exception:
            pass

        return {
            'nb_notifications': nb,
            'notifications_toast': json.dumps(notifications, cls=DjangoJSONEncoder),
            'is_vendeur': is_vendeur,
            'is_client': is_client,
            'active_url': active_url,
            'annonces_actives': annonces_vendeur if is_vendeur else (annonces_client if is_client else []),
        }
    active_url = request.resolver_match.url_name if hasattr(request, 'resolver_match') and request.resolver_match else ''
    return {'nb_notifications': 0, 'notifications_toast': '[]', 'is_vendeur': False, 'is_client': False, 'active_url': active_url, 'annonces_actives': []}


