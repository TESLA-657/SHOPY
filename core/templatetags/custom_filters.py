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

@register.filter
def whatsapp_numero(value):
    """Extrait uniquement les chiffres d'un numéro pour wa.me"""
    try:
        return ''.join(ch for ch in str(value) if ch.isdigit())
    except:
        return value

@register.filter
def lien_whatsapp(produit):
    """
    Construit le lien WhatsApp de contact vendeur avec un texte prérempli.
    Utilisation : {{ produit|lien_whatsapp }}
    """
    from urllib.parse import urlencode
    try:
        numero = ''.join(ch for ch in str(produit.vendeur.numero) if ch.isdigit())
        if not numero:
            return '#'
        try:
            prix = f"{int(produit.prix_promo) if produit.promo_active() else int(produit.prix):,}".replace(',', ' ')
        except Exception:
            prix = ''
        texte = (
            f"Bonjour {produit.vendeur.nom_boutique} 👋,\n"
            f"Je suis intéressé(e) par votre produit « {produit.nom} » "
            f"affiché à {prix} GNF sur SHOPY. Est-il toujours disponible ?"
        )
        params = urlencode({'text': texte})
        return "https://wa.me/{}?{}".format(numero, params)
    except Exception:
        return "#"

@register.filter
def afficher_etoiles(note):
    """Affiche note/5 sous forme d'étoiles pleines + vides (⭑/☆)."""
    try:
        note = int(note)
    except (TypeError, ValueError):
        note = 0
    note = max(0, min(5, note))
    return '★' * note + '☆' * (5 - note)
