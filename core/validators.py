"""
Validators personnalisés pour la sécurité des fichiers uploadés.
"""

import os
import re
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


# ============================================
# VALIDATION DES CHAMPS DE FORMULAIRE
# ============================================
# Regle metier : chaque champ doit respecter son format.
# Un numero de telephone n'accepte QUE des chiffres (les espaces,
# points et le + de l'indicatif sont toleres puis nettoyes).
# Aucun symbole, aucune lettre n'est autorise dans le numero.

# Espaces, points, tirets, parentheses et le + de l'indicatif pays sont
# tolérés (saisie lisible) puis supprimés : le numero stocké ne contient
# QUE des chiffres. Le '/' et tout autre symbole sont refusés.
_SEPARATEURS_TELEPHONE = re.compile(r'[\s.\-()+]')

_LONGUEUR_MIN_TELEPHONE = 8
_LONGUEUR_MAX_TELEPHONE = 15


def nettoyer_telephone(valeur):
    """
    Nettoie un numero de telephone : ne garde que les chiffres.

    Returns:
        str: le numero compose uniquement de chiffres.

    Raises:
        ValidationError: si un caractere non numerique est present.
    """
    if valeur is None:
        return ''

    # On neutralise d'abord les separateurs autorises.
    nettoye = _SEPARATEURS_TELEPHONE.sub('', str(valeur))

    # Il ne doit rester que des chiffres.
    if not nettoye.isdigit():
        interdits = sorted({c for c in nettoye if not c.isdigit()})
        raise ValidationError(
            "Le numero de telephone ne doit contenir que des chiffres "
            "(les espaces et le + sont acceptes). "
            "Caractere(s) interdit(s) : {0}".format(', '.join(interdits)),
            code='telephone_non_numerique',
        )

    if len(nettoye) < _LONGUEUR_MIN_TELEPHONE:
        raise ValidationError(
            'Le numero de telephone est trop court '
            '({0} chiffres minimum).'.format(_LONGUEUR_MIN_TELEPHONE),
            code='telephone_trop_court',
        )

    if len(nettoye) > _LONGUEUR_MAX_TELEPHONE:
        raise ValidationError(
            'Le numero de telephone est trop long '
            '({0} chiffres maximum).'.format(_LONGUEUR_MAX_TELEPHONE),
            code='telephone_trop_long',
        )

    return nettoye


def validate_telephone(valeur):
    """Validator Django : delegue a nettoyer_telephone()."""
    nettoyer_telephone(valeur)
    return None


def validate_email(valeur):
    """
    Valide une adresse email.

    Django fournit deja EmailValidator, mais on verifie aussi que
    l'adresse n'est pas vide et qu'elle n'a pas d'espace, source
    courante d'erreur de saisie.
    """
    if valeur is None or not str(valeur).strip():
        raise ValidationError("L'email est obligatoire.", code='email_vide')

    adresse = str(valeur).strip()
    if ' ' in adresse:
        raise ValidationError(
            "L'email ne doit pas contenir d'espace.",
            code='email_espace',
        )

    # Validation de la forme generale : local@domaine(.tld)
    if not re.match(r'^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$', adresse):
        raise ValidationError(
            "L'email n'est pas valide. Exemple : nom@domaine.com",
            code='email_invalide',
        )
    return adresse


def validate_texte_non_vide(valeur, nom_champ='Ce champ'):
    """Verifie qu'un champ texte n'est ni vide ni uniquement composé d'espaces."""
    if valeur is None or not str(valeur).strip():
        raise ValidationError(
            '{0} est obligatoire.'.format(nom_champ),
            code='champ_vide',
        )
    return str(valeur).strip()
