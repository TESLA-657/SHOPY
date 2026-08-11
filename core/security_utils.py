"""
Module de sécurité SHOPY - Utilitaires de sécurité renforcés.
"""

import re
import hashlib
import hmac
import secrets
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.conf import settings


# ============================================
# VALIDATION XSS AMÉLIORÉE
# ============================================

def sanitize_html(text):
    """
    Nettoie leHTML pour éviter les attaques XSS.
    Supprime les balises et attributs dangereux.
    """
    if not text:
        return ''
    
    # Patterns dangereux à supprimer
    dangerous_patterns = [
        r'<script[^>]*>.*?</script>',  # <script>
        r'<iframe[^>]*>.*?</iframe>',  # <iframe>
        r'javascript:',  # javascript:
        r'on\w+\s*=',  # event handlers
        r'<object[^>]*>',  # <object>
        r'<embed[^>]*>',  # <embed>
    ]
    
    cleaned = text
    for pattern in dangerous_patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.DOTALL)
    
    return cleaned.strip()


def sanitize_input(text, max_length=500):
    """
    Nettoie une entrée utilisateur générique.
    - Supprime les caractères dangereux
    - Limite la longueur
    """
    if not text:
        return ''
    
    # Conversions de base
    cleaned = str(text)
    
    # Supprimer null bytes
    cleaned = cleaned.replace('\x00', '')
    
    # Limiter longueur
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    
    # Encoder les caractères spéciaux HTML
    html_entities = {
        '<': '<',
        '>': '>',
        '"': '"',
        "'": '&#x27;',
        '&': '&amp;',
    }
    
    for char, entity in html_entities.items():
        cleaned = cleaned.replace(char, entity)
    
    return cleaned.strip()


def validate_phone(phone):
    """
    Valide un numéro de téléphone guinéen.
    """
    if not phone:
        return False
    
    # Enlever les espaces et préfixes
    phone = phone.strip().replace(' ', '')
    
    # Gestion du +224
    if phone.startswith('+224'):
        phone = phone[4:]
    
    # doit avoir 8 ou 9 chiffres
    phone = re.sub(r'\D', '', phone)  # Garder que les chiffres
    
    if len(phone) >= 8:
        return True
    
    return False


def validate_password_strength(password):
    """
    Valide la force du mot de passe.
    Retourne un dict avec is_valid et erreurs.
    """
    errors = []
    
    if len(password) < 8:
        errors.append('Minimum 8 caractères')
    
    if not re.search(r'[A-Za-z]', password):
        errors.append('Au moins une lettre')
    
    if not re.search(r'\d', password):
        errors.append('Au moins un chiffre')
    
    # Bonus: caractères spéciaux
    has_special = bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password))
    
    return {
        'is_valid': len(errors) == 0,
        'errors': errors,
        'strength': 'fort' if has_special and len(password) >= 10 else 'moyen'
    }


# ============================================
# GÉNÉRATION DE TOKES SÉCURISÉS
# ============================================

def generate_secure_token(length=32):
    """
    Génère un token aléatoire sécurisé.
    """
    return secrets.token_urlsafe(length)


def generate_verification_code(length=6):
    """
    Génère un code de vérification numérique.
    """
    return ''.join(secrets.choice('0123456789') for _ in range(length))


def hash_data(data, salt=None):
    """
    Hashe des données avec un salt.
    """
    if salt is None:
        salt = settings.SECRET_KEY
    
    return hmac.new(
        salt.encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()


def verify_hash(data, hash_value, salt=None):
    """
    Vérifie un hash.
    """
    expected = hash_data(data, salt)
    return hmac.compare_digest(expected, hash_value)


# ============================================
# VALIDATION DES ENTRÉES
# ============================================

def validate_email_format(email):
    """
    Valide le format d'un email.
    """
    try:
        validate_email(email)
        return True
    except ValidationError:
        return False


def validate_required_fields(data, required_fields):
    """
    Valide que tous les champs requis sont présents et non vides.
    """
    missing = []
    empty = []
    
    for field in required_fields:
        if field not in data:
            missing.append(field)
        elif not data.get(field):
            empty.append(field)
    
    return {
        'is_valid': len(missing) == 0 and len(empty) == 0,
        'missing': missing,
        'empty': empty,
    }


# ============================================
# PROTECTION UPLOAD
# ============================================

ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
ALLOWED_DOCUMENT_EXTENSIONS = {'pdf', 'doc', 'docx'}

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def validate_file_upload(file):
    """
    Valide un fichier uploadé.
    """
    # Vérifier la taille
    if file.size > MAX_FILE_SIZE:
        return {
            'is_valid': False,
            'error': f'Fichier trop volumineux. Maximum: {MAX_FILE_SIZE // 1024 // 1024}MB'
        }
    
    # Vérifier l'extension
    ext = file.name.split('.')[-1].lower() if '.' in file.name else ''
    
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return {
            'is_valid': False,
            'error': f'Extension non autorisée. Utilisez: {", ".join(ALLOWED_IMAGE_EXTENSIONS)}'
        }
    
    return {'is_valid': True}


# ============================================
# LOGGING SÉCURITÉ
# ============================================

import logging

# Configuration logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def log_security_event(request, event_type, details=None):
    """
    Log un événement de sécurité.
    """
    from django.utils import timezone
    
    logger = logging.getLogger('shopy.security')
    
    ip = request.META.get('REMOTE_ADDR', 'unknown')
    user = request.user.username if request.user.is_authenticated else 'anonymous'
    
    message = f"[{event_type}] User: {user}, IP: {ip}"
    
    if details:
        message += f", Details: {details}"
    
    logger.warning(message)


def log_failed_login(request, username):
    """
    Log une connexion échouée.
    """
    log_security_event(
        request, 
        'FAILED_LOGIN', 
        f'Username: {username}'
    )


def log_suspicious_activity(request, activity_type):
    """
    Log une activity suspecte.
    """
    log_security_event(
        request,
        f'SUSPICIOUS_{activity_type.upper()}',
        activity_type
    )


# ============================================
# CAPTCHA SIMPLE (Anti-bot)
# ============================================

import random


def generate_captcha_question():
    """
    Génère une question mathématique CAPTCHA simple.
    Retourne un dict avec question et réponse.
    """
    # Opérations simples (addition, soustraction, multiplication)
    operations = [
        ('+', lambda a, b: a + b),
        ('-', lambda a, b: a - b),
        ('x', lambda a, b: a * b),
    ]
    
    op_name, op_func = random.choice(operations)
    
    if op_name == '+':
        a = random.randint(1, 20)
        b = random.randint(1, 20)
    elif op_name == '-':
        a = random.randint(10, 30)
        b = random.randint(1, a)  # Résultat positif
    else:  # multiplication
        a = random.randint(2, 9)
        b = random.randint(2, 9)
    
    answer = op_func(a, b)
    question = f"{a} {op_name} {b} = ?"
    
    return {
        'question': question,
        'answer': str(answer),
    }


def validate_captcha(user_answer, expected_answer):
    """
    Valide la réponse CAPTCHA.
    """
    if not user_answer or not expected_answer:
        return False
    
    # Nettoyer les entrées
    user_answer = str(user_answer).strip()
    expected_answer = str(expected_answer).strip()
    
    return user_answer == expected_answer
