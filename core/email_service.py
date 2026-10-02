"""
Service d'envoi d'emails de SHOPY — point d'entree central.

Ce module isole toute la logique d'envoi. Les vues Django appellent
`envoyer()` et ne connaissent ni le SDK Resend, ni le SMTP, ni la cle
API, ni le format des payloads.

Choix automatique du transport :
    1. `envoyer()`  — point d'entree central (a utiliser par le code) ;
    2. Resend       — transport principal si RESEND_API_KEY est definie ;
    3. SMTP Django  — repli automatique sinon (comportement historique).

La cle API provient EXCLUSIVEMENT de la variable d'environnement
RESEND_API_KEY, lue dans marketplace/settings.py. Elle n'est jamais
codee en dur et ne doit jamais etre commitee.

Note : le SDK officiel `resend` lit la cle dans la variable
d'environnement au moment de l'import. On la reaffecte explicitement
ici depuis les settings pour que la configuration Django reste la
source unique de verite.

Par defaut, `envoyer()` n leve jamais d'exception : un email non parti
ne doit pas faire echouer une commande, un paiement ou une inscription.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)


# ============================================
# CONFIGURATION
# ============================================

def resend_est_configure():
    """Retourne True si l'envoi via Resend est possible."""
    return bool(getattr(settings, 'RESEND_API_KEY', '')) and bool(
        getattr(settings, 'RESEND_ENABLED', True)
    )


def _obtenir_client():
    """
    Importe le SDK resend et lui injecte la cle API.

    L'import est volontairement local (et non au niveau du module) :
    si la variable RESEND_API_KEY est absente, on ne veut pas que
    l'import du SDK echoue au demarrage de Django.
    """
    import resend

    cle = getattr(settings, 'RESEND_API_KEY', '')
    if not cle:
        raise RuntimeError(
            "RESEND_API_KEY n'est pas definie. Ajoutez-la a votre "
            "variable d'environnement (fichier .env en local, "
            "dashboard Render en production)."
        )

    # Le SDK lit resend.api_key pour l'en-tete Authorization.
    resend.api_key = cle

    # Permet de pointer vers une URL differente si besoin (tests, mock).
    api_url = getattr(settings, 'RESEND_API_URL', '')
    if api_url:
        resend.api_url = api_url

    return resend


def expediteur():
    """Construit l'adresse d'expedition au format attendu par Resend."""
    nom = getattr(settings, 'RESEND_FROM_NAME', '')
    adresse = getattr(settings, 'RESEND_FROM_EMAIL', '')
    if nom:
        return '{0} <{1}>'.format(nom, adresse)
    return adresse


# ============================================
# ENVOI
# ============================================

def envoyer_email(destinataire, sujet, corps_texte='', corps_html=None,
                  reply_to=None, copie=None):
    """
    Envoie un email via Resend.

    Args:
        destinataire (str): adresse email du destinataire.
        sujet (str): objet de l'email.
        corps_texte (str): contenu en texte brut.
        corps_html (str): contenu HTML (optionnel).
        reply_to (str|list): adresse(s) de reponse (optionnel).
        copie (str|list): copie(s) carbone (optionnel).

    Returns:
        dict: reponse de l'API Resend (contient l'identifiant 'id').

    Raises:
        RuntimeError: si la cle API est absente ou l'envoi desactive.
        Exception: toute erreur renvoyee par l'API Resend.
    """
    if not getattr(settings, 'RESEND_ENABLED', True):
        raise RuntimeError(
            "L'envoi d'emails est desactive (RESEND_ENABLED=False)."
        )

    resend = _obtenir_client()

    # Resend attend "to" sous forme de liste.
    if isinstance(destinataire, (list, tuple, set)):
        liste_to = list(destinataire)
    else:
        liste_to = [destinataire]

    params = {
        'from': expediteur(),
        'to': liste_to,
        'subject': sujet,
    }
    if corps_texte:
        params['text'] = corps_texte
    if corps_html:
        params['html'] = corps_html
    if reply_to:
        params['reply_to'] = reply_to
    if copie:
        # Attention : ne pas reutiliser liste_to ici, sinon les
        # destinataires finiraient en copie carbone.
        params['cc'] = _vers_liste(copie)

    logger.info(
        "Envoi d'un email via Resend a %s (sujet : %s)",
        liste_to, sujet,
    )
    return resend.Emails.send(params)


# ============================================
# TRANSPORT SMTP (repli)
# ============================================

def smtp_est_configure():
    """
    Retourne True si un envoi SMTP est techniquement possible.

    On se base sur le backend configure dans les settings plutot que
    sur la presence de credentials : en developpement le backend
    "console" est parfaitement fonctionnel (il affiche l'email dans
    le terminal), ce qui evite deconsiderer le repli a tort.
    """
    backend = getattr(settings, 'EMAIL_BACKEND', '') or ''
    return bool(backend)


def _vers_liste(adresses):
    """Normalise un destinataire (str ou collection) en liste de str."""
    if adresses is None:
        return []
    if isinstance(adresses, str):
        return [adresses] if adresses.strip() else []
    return [a for a in adresses if a and str(a).strip()]


def envoyer_email_smtp(destinataire, sujet, corps_texte='', corps_html=None,
                       from_email=None, reply_to=None, copie=None,
                       copie_cache=None, fail_silently=True):
    """
    Envoie un email via le backend SMTP Django (repli de Resend).

    Le comportement est aligne sur les appels `send_mail()` existants
    dans le projet : aucune exception ne remonte (fail_silently=True
    par defaut), afin de ne jamais casser une action metier.

    Returns:
        int: nombre d'emails envoyes (0 en cas d'echec silencieux).
    """
    liste_to = _vers_liste(destinataire)
    if not liste_to:
        return 0

    return send_mail(
        subject=sujet,
        message=corps_texte or '',
        from_email=from_email or getattr(
            settings, 'DEFAULT_FROM_EMAIL', 'noreply@shopy-guinee.com'
        ),
        recipient_list=liste_to,
        html_message=corps_html or None,
        reply_to=reply_to or None,
        cc=_vers_liste(copie) or None,
        bcc=_vers_liste(copie_cache) or None,
        fail_silently=fail_silently,
    )


# ============================================
# POINT D'ENTREE CENTRAL
# ============================================

def transport_actif():
    """
    Retourne le transport qui sera utilise : 'resend', 'smtp' ou 'aucun'.

    Resend est prioritaire des lors que la cle est configuree et que
    l'envoi n'a pas ete desactive explicitement.
    """
    if resend_est_configure():
        return 'resend'
    if smtp_est_configure():
        return 'smtp'
    return 'aucun'


def envoyer(destinataire, sujet, corps_texte='', corps_html=None,
            reply_to=None, copie=None, copie_cache=None,
            from_email=None, fail_silently=True):
    """
    Point d'entree central pour l'envoi d'emails de SHOPY.

    Choisit automatiquement le transport :
        1. Resend si RESEND_API_KEY est configuree (transport principal) ;
        2. sinon, repli sur le SMTP Django deja configure dans le projet.

    Cette fonction est concue pour remplacer progressivement les appels
    `send_mail()` disperses dans les vues, sans changer leur comportement.

    Args:
        destinataire (str|list): adresse(s) du(des) destinataire(s).
        sujet (str): objet de l'email.
        corps_texte (str): contenu en texte brut.
        corps_html (str): contenu HTML (optionnel).
        reply_to (str|list): adresse(s) de reponse.
        copie (str|list): copie(s) carbone.
        copie_cache (str|list): copie(s) cachees.
        from_email (str): expediteur (defaut : DEFAULT_FROM_EMAIL).
        fail_silently (bool): si True, une erreur d'envoi ne leve
            jamais d'exception (comportement historique de SHOPY).

    Returns:
        dict: {'envoye': bool, 'transport': 'resend'|'smtp'|'aucun',
               'erreur': str|None}
    """
    transport = transport_actif()

    if transport == 'aucun':
        message = (
            "Aucun transport d'email configure : definissez "
            "RESEND_API_KEY (ou un EMAIL_BACKEND) pour activer l'envoi."
        )
        logger.warning(message)
        if not fail_silently:
            raise RuntimeError(message)
        return {'envoye': False, 'transport': 'aucun', 'erreur': message}

    if transport == 'resend':
        try:
            envoyer_email(
                destinataire=destinataire,
                sujet=sujet,
                corps_texte=corps_texte,
                corps_html=corps_html,
                reply_to=reply_to,
                copie=copie,
            )
            return {'envoye': True, 'transport': 'resend', 'erreur': None}
        except Exception as exc:
            # Le repli SMTP n'est PAS tente ici : Resend etant configure,
            # une erreur signale un vrai probleme de configuration qu'il
            # vaut mieux voir dans les logs que de masquer.
            logger.error(
                "Echec de l'envoi via Resend a %s : %s", destinataire, exc
            )
            if not fail_silently:
                raise
            return {'envoye': False, 'transport': 'resend', 'erreur': str(exc)}

    # Repli SMTP
    try:
        envoyes = envoyer_email_smtp(
            destinataire=destinataire,
            sujet=sujet,
            corps_texte=corps_texte,
            corps_html=corps_html,
            from_email=from_email,
            reply_to=reply_to,
            copie=copie,
            copie_cache=copie_cache,
            fail_silently=fail_silently,
        )
        return {
            'envoye': bool(envoyes),
            'transport': 'smtp',
            'erreur': None,
        }
    except Exception as exc:
        logger.error(
            "Echec de l'envoi via SMTP a %s : %s", destinataire, exc
        )
        if not fail_silently:
            raise
        return {'envoye': False, 'transport': 'smtp', 'erreur': str(exc)}


# ============================================
# EMAILS DE CYCLE DE VIE DU COMPTE
# ============================================
# Ces emails couvrent l'inscription et la securite du compte.
# Contrairement aux notifications transactionnelles (commande, paiement),
# un echec ici doit etre VISIBLE : si l'utilisateur ne recoit pas son
# code de reinitialisation, il est bloque. On utilise donc
# fail_silently=False et l'appelant decide quoi afficher.

def _liste_boutique(nom_boutique, ville=''):
    return nom_boutique + (f' ({ville})' if ville else '')


def email_bienvenue_client(prenom_ou_nom, email_destinataire, lien=None):
    """Email de bienvenue envoye apres la creation d'un compte client."""
    corps_texte = (
        f"Bonjour {prenom_ou_nom},\n\n"
        "Votre compte SHOPY est cree. Vous pouvez maintenant parcourir le "
        "catalogue et commander directement.\n\n"
        "Au plaisir,\n"
        "- L'equipe SHOPY"
    )
    if lien:
        corps_texte += f"\n\nAccedez a votre espace : {lien}"
    return envoyer(
        destinataire=email_destinataire,
        sujet="Bienvenue sur SHOPY - votre compte est actif",
        corps_texte=corps_texte,
        fail_silently=False,
    )


def email_bienvenue_vendeur(nom_boutique, email_destinataire, ville='',
                           lien=None):
    """Email envoye au vendeur apres la creation de sa boutique."""
    corps_texte = (
        f"Bonjour {nom_boutique},\n\n"
        f"Votre boutique {_liste_boutique(nom_boutique, ville)} est "
        "enregistree sur SHOPY.\n\n"
        "Elle sera validee par notre equipe tres rapidement. Vous pourrez "
        "ensuite ajouter vos produits et recevoir vos commandes.\n\n"
        "- L'equipe SHOPY"
    )
    if lien:
        corps_texte += f"\n\nAccedez a votre espace : {lien}"
    return envoyer(
        destinataire=email_destinataire,
        sujet="Votre boutique SHOPY est enregistree",
        corps_texte=corps_texte,
        fail_silently=False,
    )


def email_code_verification(email_destinataire, code, minutes=10):
    """Email contenant le code de reinitialisation de mot de passe."""
    corps_texte = (
        "Bonjour,\n\n"
        f"Votre code de verification SHOPY est : {code}\n\n"
        f"Il est valable {minutes} minutes.\n"
        "Si vous n'etes pas a l'origine de cette demande, ignorez cet email.\n\n"
        "- L'equipe SHOPY"
    )
    return envoyer(
        destinataire=email_destinataire,
        sujet="Votre code de verification SHOPY",
        corps_texte=corps_texte,
        fail_silently=False,
    )


def envoyer_email_de_test(destinataire):
    """
    Envoie un email de verification simple.

    Sert uniquement a valider que SHOPY sait envoyer un email via
    Resend. Aucun impact metier : appele manuellement via la commande
    de gestion `tester_resend`.
    """
    sujet = 'SHOPY - Test d\'envoi via Resend'
    corps_texte = (
        "Bonjour,\n\n"
        "Ceci est un email de test envoye par SHOPY via Resend.\n"
        "Si vous le lisez, la configuration est operationnelle.\n\n"
        "Date d'envoi : {0}\n".format(timezone.now().strftime('%d/%m/%Y %H:%M'))
    )
    corps_html = (
        '<div style="font-family:Segoe UI,Arial,sans-serif;max-width:520px">'
        '<h2 style="color:#059669;margin:0 0 12px">SHOPY</h2>'
        '<p>Ceci est un email de test envoye via <strong>Resend</strong>.</p>'
        '<p>Si vous le lisez, la configuration est operationnelle.</p>'
        '</div>'
    )
    return envoyer_email(
        destinataire=destinataire,
        sujet=sujet,
        corps_texte=corps_texte,
        corps_html=corps_html,
    )
