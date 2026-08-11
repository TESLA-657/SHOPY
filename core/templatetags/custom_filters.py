from django import template

register = template.Library()

@register.filter
def with_suffix(valeur):
    """Ajoute un séparateur de milliers avec espace"""
    try:
        valeur = int(valeur)
        return f"{valeur:,}".replace(",", " ")
    except:
        return valeur

@register.filter
def format_prix(valeur):
    try:
        valeur = int(valeur)
        return f"{valeur:,}".replace(",", " ")
    except:
        return valeur

@register.filter
def multiply(value, arg):
    """Multiplie la valeur par l'argument"""
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def subtract(value, arg):
    """Soustrait l'argument de la valeur"""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def sub(value, arg):
    """Alias pour subtract - soustrait l'argument de la valeur"""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def div(value, arg):
    """Divise la valeur par l'argument"""
    try:
        if int(arg) == 0:
            return 0
        return int(value) / int(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter
def mul(value, arg):
    """Multiplie la valeur par l'argument"""
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0
