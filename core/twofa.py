"""
Module 2FA (Two-Factor Authentication) pour SHOPY.
"""

import random
import string
from django.core.cache import cache
from django.conf import settings


def generate_2fa_code(length=6):
    """Génère un code 2FA à 6 chiffres."""
    return ''.join(random.choices(string.digits, k=length))


def send_2fa_sms(phone_number, code):
    """
    Envoie le code 2FA par SMS.
    À intégrer avec votre provider SMS (Orange, etc.)
    """
    # Log pour développement
    print(f"📱 SMS 2FA vers {phone_number}: Votre code est {code}")
    
    # À remplacer par真正的 API SMS
    # try:
    #     response = requests.post(
    #         'https://api.sms.com/send',
    #         data={
    #             'to': phone_number,
    #             'message': f'Votre code SHOPY: {code}'
    #         }
    #     )
    #     return response.status_code == 200
    # except:
    #     return False
    
    return True


def initiate_2fa(user, phone_number):
    """
    Initie le processus 2FA.
    Génère et envoie le code.
    """
    # Générer code
    code = generate_2fa_code()
    
    # Stocker en cache (valide 5 minutes)
    cache_key = f'2fa_{user.id}'
    cache.set(cache_key, code, 300)
    
    # Envoyer SMS
    send_2fa_sms(phone_number, code)
    
    return True


def verify_2fa(user, code):
    """
    Vérifie le code 2FA.
    """
    cache_key = f'2fa_{user.id}'
    stored_code = cache.get(cache_key)
    
    if not stored_code:
        return False, "Code expiré. Réessayez."
    
    if stored_code == code:
        # Supprimer le code après vérification
        cache.delete(cache_key)
        return True, "Vérifié"
    
    return False, "Code invalide"


def is_2fa_enabled(user):
    """Vérifie si 2FA est activé pour l'utilisateur."""
    # À implémenter avec modèle utilisateur
    return getattr(user, 'twofa_enabled', False)


def enable_2fa(user, phone_number):
    """Active 2FA pour l'utilisateur."""
    # Stocker le numéro pour 2FA
    cache_key = f'2fa_setup_{user.id}'
    cache.set(cache_key, phone_number, 3600)  # 1 heure pour confirmer
    
    # Envoyer code de confirmation
    code = generate_2fa_code()
    cache.set(f'2fa_confirm_{user.id}', code, 3600)
    
    send_2fa_sms(phone_number, code)
    
    return True


def confirm_2fa_setup(user, code):
    """Confirme l'activation 2FA."""
    cache_key = f'2fa_confirm_{user.id}'
    stored_code = cache.get(cache_key)
    
    if stored_code == code:
        cache.delete(cache_key)
        # Activer 2FA dans le modèle utilisateur
        # user.twofa_enabled = True
        # user.save()
        return True, "2FA activé"
    
    return False, "Code invalide"


def disable_2fa(user):
    """Désactive 2FA pour l'utilisateur."""
    # user.twofa_enabled = False
    # user.save()
    return True
