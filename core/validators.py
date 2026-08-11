"""
Validators personnalisés pour la sécurité des fichiers uploadés.
"""

import os
from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible

# Types MIME autorisés pour les images
ALLOWED_IMAGE_MIME_TYPES = [
    'image/jpeg',
    'image/png', 
    'image/gif',
    'image/webp',
]

# Extensions autorisées
ALLOWED_IMAGE_EXTENSIONS = [
    '.jpg', '.jpeg', '.png', '.gif', '.webp'
]

# Taille maximale: 5MB
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB en bytes


@deconstructible
class SecureImageValidator:
    """
    Validator qui vérifie:
    - Type MIME (images seulement)
    - Extension sécurisée
    - Taille maximale
    """
    
    def __init__(self, max_size=MAX_FILE_SIZE):
        self.max_size = max_size
    
    def __call__(self, file):
        # Vérifier la taille
        if file.size > self.max_size:
            raise ValidationError(
                f'Taille maximale dépassée. Maximum: {self.max_size // (1024*1024)}MB',
                code='file_too_large'
            )
        
        # Vérifier l'extension
        file_name, file_ext = os.path.splitext(file.name)
        if file_ext.lower() not in ALLOWED_IMAGE_EXTENSIONS:
            raise ValidationError(
                f'Extension non autorisée. Utilisez: {", ".join(ALLOWED_IMAGE_EXTENSIONS)}',
                code='invalid_extension'
            )
        
        # Vérifier le type MIME (si possible)
        if hasattr(file, 'content_type'):
            if file.content_type not in ALLOWED_IMAGE_MIME_TYPES:
                raise ValidationError(
                    f'Type de fichier non autorisé. Utilisez une image (JPEG, PNG, GIF, WebP)',
                    code='invalid_mime_type'
                )
    
    def __eq__(self, other):
        return (
            isinstance(other, SecureImageValidator) and 
            self.max_size == other.max_size
        )


def validate_secure_image(file):
    """
    Fonction validator compatible avec Model field.
    """
    validator = SecureImageValidator()
    validator(file)
    return None


def validate_file_size(file):
    """Valide seulement la taille du fichier"""
    if file.size > MAX_FILE_SIZE:
        raise ValidationError(
            f'Le fichier dépasse la taille maximale de {MAX_FILE_SIZE // (1024*1024)}MB',
            code='file_too_large'
        )
