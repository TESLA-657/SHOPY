"""
Module Audit Trail pour SHOPY.
Enregistre toutes les actions importantes dans la base de données.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class AuditLog(models.Model):
    """Modèle pour enregistrer les actions utilisateur."""
    
    ACTION_TYPES = [
        ('login_vendor', 'Connexion vendeur'),
        ('login_client', 'Connexion client'),
        ('logout', 'Déconnexion'),
        ('signup_vendor', 'Inscription vendeur'),
        ('signup_client', 'Inscription client'),
        ('page_view', 'Page vue'),
        ('product_view', 'Vue produit'),
        ('order_placed', 'Commande passée'),
        ('payment', 'Paiement'),
        ('product_add', 'Ajout produit'),
        ('product_edit', 'Modification produit'),
        ('product_delete', 'Suppression produit'),
        ('admin_action', 'Action admin'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=30, choices=ACTION_TYPES)
    details = models.TextField(blank=True)
    ip_address = models.CharField(max_length=50)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user} - {self.action} - {self.timestamp}"


def log_action(request, action, details=''):
    """
    Enregistre une action dans l'audit trail.
    """
    user = request.user if request.user.is_authenticated else None
    ip = request.META.get('REMOTE_ADDR', 'unknown')
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:200]
    
    AuditLog.objects.create(
        user=user,
        action=action,
        details=details,
        ip_address=ip,
        user_agent=user_agent,
    )


def get_user_actions(user, days=7):
    """Récupère les actions d'un utilisateur."""
    from datetime import timedelta
    since = timezone.now() - timedelta(days=days)
    return AuditLog.objects.filter(
        user=user,
        timestamp__gte=since
    ).order_by('-timestamp')


def get_all_actions(days=7, limit=100):
    """Récupère toutes les actions récentes."""
    from datetime import timedelta
    since = timezone.now() - timedelta(days=days)
    return AuditLog.objects.filter(
        timestamp__gte=since
    ).order_by('-timestamp')[:limit]
