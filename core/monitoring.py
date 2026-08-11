"""
Module Monitoring /Santé serveur pour SHOPY.
"""

import os
import psutil
import platform
from django.conf import settings
from django.utils import timezone


def get_server_health():
    """
    Retourne l'état de santé du serveur.
    """
    return {
        'status': 'healthy',
        'timestamp': timezone.now(),
        'cpu': get_cpu_usage(),
        'memory': get_memory_usage(),
        'disk': get_disk_usage(),
        'uptime': get_uptime(),
    }


def get_cpu_usage():
    """Retourne l'utilisation CPU."""
    try:
        return {
            'percent': psutil.cpu_percent(interval=0.1),
            'count': psutil.cpu_count(),
        }
    except:
        return {'percent': 0, 'count': 1}


def get_memory_usage():
    """Retourne l'utilisation mémoire."""
    try:
        mem = psutil.virtual_memory()
        return {
            'total': mem.total,
            'used': mem.used,
            'free': mem.free,
            'percent': mem.percent,
        }
    except:
        return {'total': 0, 'used': 0, 'free': 0, 'percent': 0}


def get_disk_usage():
    """Retourne l'utilisation disque."""
    try:
        disk = psutil.disk_usage('/')
        return {
            'total': disk.total,
            'used': disk.used,
            'free': disk.free,
            'percent': disk.percent,
        }
    except:
        return {'total': 0, 'used': 0, 'free': 0, 'percent': 0}


def get_uptime():
    """Retourne le uptime du serveur."""
    try:
        boot_time = psutil.boot_time()
        import time
        uptime_seconds = time.time() - boot_time
        hours = int(uptime_seconds // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        return f"{hours}h {minutes}min"
    except:
        return "Inconnu"


def get_server_info():
    """Retourne les informations serveur."""
    return {
        'platform': platform.system(),
        'platform_version': platform.version(),
        'architecture': platform.machine(),
        'python_version': platform.python_version(),
    }


def check_health():
    """
    Vérifie si le serveur va bien.
    Retourne False si problème.
    """
    health = get_server_health()
    
    # Alerte si CPU > 90%
    if health['cpu']['percent'] > 90:
        return False
    
    # Alerte si mémoire > 90%
    if health['memory']['percent'] > 90:
        return False
    
    # Alerte si disque > 90%
    if health['disk']['percent'] > 90:
        return False
    
    return True


def get_alerts():
    """
    Retourne les alertes actives.
    """
    alerts = []
    health = get_server_health()
    
    if health['cpu']['percent'] > 80:
        alerts.append(f"CPU élevé: {health['cpu']['percent']}%")
    
    if health['memory']['percent'] > 80:
        alerts.append(f"Mémoire élevée: {health['memory']['percent']}%")
    
    if health['disk']['percent'] > 80:
        alerts.append(f"Disque plein: {health['disk']['percent']}%")
    
    return alerts
