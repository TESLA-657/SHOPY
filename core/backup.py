"""
Module Backup automatique pour SHOPY.
"""

import os
import shutil
import datetime
from django.conf import settings
from django.core.management import call_command


def create_backup():
    """
    Crée une sauvegarde de la base de données.
    """
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = getattr(settings, 'BACKUP_DIR', os.path.join(settings.BASE_DIR, 'backups'))
    
    # Créer le répertoire si inexistant
    os.makedirs(backup_dir, exist_ok=True)
    
    # Nom du fichier
    db_path = settings.DATABASES['default']['NAME']
    backup_file = os.path.join(backup_dir, f'shopy_backup_{timestamp}.sqlite3')
    
    # Copier la base
    if os.path.exists(db_path):
        shutil.copy2(db_path, backup_file)
        return backup_file
    
    return None


def list_backups(days=30):
    """
    Liste les sauvegardes récentes.
    """
    backup_dir = getattr(settings, 'BACKUP_DIR', os.path.join(settings.BASE_DIR, 'backups'))
    
    if not os.path.exists(backup_dir):
        return []
    
    from datetime import timedelta
    cutoff = datetime.datetime.now() - timedelta(days=days)
    backups = []
    
    for f in os.listdir(backup_dir):
        if f.startswith('shopy_backup_') and f.endswith('.sqlite3'):
            path = os.path.join(backup_dir, f)
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(path))
            if mtime > cutoff:
                backups.append({
                    'file': f,
                    'date': mtime,
                    'size': os.path.getsize(path)
                })
    
    return sorted(backups, key=lambda x: x['date'], reverse=True)


def cleanup_old_backups(keep=7):
    """
    Supprime les anciennes sauvegardes.
    Garde les 'keep' plus récentes.
    """
    backups = list_backups(days=365)
    
    if len(backups) <= keep:
        return 0
    
    backup_dir = getattr(settings, 'BACKUP_DIR', os.path.join(settings.BASE_DIR, 'backups'))
    deleted = 0
    
    for backup in backups[keep:]:
        path = os.path.join(backup_dir, backup['file'])
        try:
            os.remove(path)
            deleted += 1
        except:
            pass
    
    return deleted
