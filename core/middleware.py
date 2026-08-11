"""
Middleware de rate limiting pour protéger contre les attaques brute-force.
"""

import time
from collections import defaultdict
from django.core.cache import cache
from django.http import JsonResponse


class RateLimitMiddleware:
    """
    Middleware qui limite les requêtes par IP pour éviter les attaques:
    - Brute force sur les formulaires de connexion
    - Déni de service (DDoS)
    - Scraping excessif
    """
    
    # Configuration par défaut
    DEFAULT_RATE = 60  # requêtes par minute
    DEFAULT_BURST = 10  # requêtes par seconde
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Chemins exemptés (pas de rate limiting)
        self.exempt_paths = [
            '/static/',
            '/media/',
            '/admin/',
        ]
        # Views avec rate limit personnalisé
        self.custom_limits = {
            'connexion_vendeur': {'rate': 5, 'period': 300},  # 5 tentatives en 5 min
            'connexion_client': {'rate': 5, 'period': 300},
            'inscription_vendeur': {'rate': 3, 'period': 3600},  # 3 inscriptions/heure
            'inscription_client': {'rate': 3, 'period': 3600},
        }
    
    def __call__(self, request):
        # Vérifier si exempté
        if self.is_exempt(request):
            return self.get_response(request)
        
        # Vérifier le rate limit
        check_result = self.check_rate_limit(request)
        if not check_result['allowed']:
            return JsonResponse({
                'error': 'Trop de requêtes. Veuillez patienter.',
                'retry_after': check_result['retry_after']
            }, status=429)
        
        response = self.get_response(request)
        
        # Ajouter headers de rate limit
        response['X-RateLimit-Limit'] = str(check_result['limit'])
        response['X-RateLimit-Remaining'] = str(check_result['remaining'])
        response['X-RateLimit-Reset'] = str(check_result['reset'])
        
        return response
    
    def is_exempt(self, request):
        """Vérifie si le chemin est exempté"""
        path = request.path
        for exempt_path in self.exempt_paths:
            if path.startswith(exempt_path):
                return True
        return False
    
    def get_client_ip(self, request):
        """Extrait l'IP du client"""
        # Tester via proxy
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip
    
    def get_rate_limit(self, request):
        """Détermine le rate limit pour cette requête"""
        path = request.path
        
        # Vérifier les limites personnalisées
        for view_name, limit in self.custom_limits.items():
            if view_name in path:
                return limit['rate'], limit['period']
        
        # Retourner limite par défaut
        return self.DEFAULT_RATE, 60
    
    def check_rate_limit(self, request):
        """
        Vérifie si la requête est permise selon le rate limit.
        Utilise le cache Django pour stocker les compteurs.
        """
        client_ip = self.get_client_ip(request)
        rate, period = self.get_rate_limit(request)
        
        cache_key = f'rl_{client_ip}_{int(time.time() // period)}'
        
        # Récupérer ou initiale le compteur
        count = cache.get(cache_key, 0)
        remaining = max(0, rate - count)
        
        allowed = count < rate
        retry_after = 0
        
        if allowed:
            # Incrémenter le compteur
            cache.set(cache_key, count + 1, period)
            remaining = max(0, rate - count - 1)
        else:
            # Calculer le temps d'attente
            current_period = int(time.time() // period)
            next_reset = (current_period + 1) * period
            retry_after = int(next_reset - time.time())
        
        return {
            'allowed': allowed,
            'limit': rate,
            'remaining': remaining,
            'reset': int(time.time()) + period,
            'retry_after': retry_after,
        }


def rate_limit_view(max_attempts=5, lockout_time=300):
    """
    Décorateur pour limiter spécifiquement une vue.
    Utilise le cache pour stocker les tentatives.
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            from django.contrib import messages
            
            # Clé unique pour cet utilisateur
            if request.user.is_authenticated:
                cache_key = f'rl_{view_func.__name__}_{request.user.id}'
            else:
                ip = request.META.get('REMOTE_ADDR', 'unknown')
                cache_key = f'rl_{view_func.__name__}_{ip}'
            
            # Vérifier les tentatives
            attempts = cache.get(cache_key, 0)
            
            if attempts >= max_attempts:
                # Utilisateur bloqué
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': f'Trop de tentatives. Réessayez dans {lockout_time//60} minutes.'
                    }, status=429)
                else:
                    messages.error(
                        request, 
                        f'Trop de tentatives. Veuillezpatienter {lockout_time//60} minute(s).'
                    )
                    # Retourner None pour que la vue gère la redirection
                    return None
            
            # Exécuter la vue
            try:
                result = view_func(request, *args, **kwargs)
                
                # Si succès, reset les tentatives
                if hasattr(result, 'status_code') and result.status_code in [200, 302]:
                    cache.delete(cache_key)
                
                return result
            except Exception as e:
                # En cas d'erreur, incrementer le compteur
                cache.set(cache_key, attempts + 1, lockout_time)
                raise
        
        return wrapper
    return decorator


# Configuration des limites par vue
RATE_LIMITS = {
    # Connexion: 5 tentatives toutes les 5 minutes
    'connexion_vendeur': {'attempts': 5, 'lockout': 300},
    'connexion_client': {'attempts': 5, 'lockout': 300},
    
    # Inscription: 3 toutes les heures
    'inscription_vendeur': {'attempts': 3, 'lockout': 3600},
    'inscription_client': {'attempts': 3, 'lockout': 3600},
    
    # Paiement: 10 tentatives toutes les 10 minutes
    'payer_commande': {'attempts': 10, 'lockout': 600},
    'payer_panier': {'attempts': 10, 'lockout': 600},
}


# ============================================
# SECURITY HEADERS MIDDLEWARE
# ============================================

class SecurityHeadersMiddleware:
    """
    Ajoute des en-têtes de sécurité HTTP pour protéger contre:
    - XSS
    - Clickjacking
    - MIME sniffing
    - Cross-site scripting
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Headers de sécurité
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Only set CSP header in production (DEBUG=False)
        # In development, let the browser handle requests freely
        from django.conf import settings
        if not settings.DEBUG:
            response['Content-Security-Policy'] = (
                "default-src 'self'; "
                "img-src 'self' data: https:; "
                "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
                "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
                "connect-src 'self' http: https:; "
            )
        
        return response


# ============================================
# SESSION TIMEOUT MIDDLEWARE
# ============================================

class SessionTimeoutMiddleware:
    """
    Déconnexion automatique après inactivité.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Timeout en secondes (30 minutes)
        self.timeout = 1800
    
    def __call__(self, request):
        if request.user.is_authenticated:
            # Vérifier last activity
            last_activity = request.session.get('last_activity')
            import time
            if last_activity:
                elapsed = time.time() - last_activity
                if elapsed > self.timeout:
                    # Session expirée
                    from django.contrib.auth import logout
                    logout(request)
                    return self.get_response(request)
            
            # Mettre à jour last activity
            request.session['last_activity'] = time.time()
        
        return self.get_response(request)


# ============================================
# ADMIN IP RESTRICTION MIDDLEWARE
# ============================================

class AdminIPRestrictionMiddleware:
    """
    Limite l'accès admin à certaines IPs.
    """
    
    # IPs autorisées pour admin (à configurer)
    ADMIN_IPS = ['127.0.0.1', '::1']
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Vérifier si chemin admin
        if request.path.startswith('/admin'):
            client_ip = request.META.get('REMOTE_ADDR')
            if client_ip not in self.ADMIN_IPS:
                from django.http import HttpResponseForbidden
                return HttpResponseForbidden('Accès admin refusé')
        
        return self.get_response(request)
