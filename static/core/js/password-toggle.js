/* ============================================================
   SHOPY — Afficher / masquer le mot de passe (bouton « œil »)
   Ajoute automatiquement une icône à côté de chaque champ
   <input type="password"> présent dans la page.
   Aucune dépendance externe (ni jQuery ni Bootstrap).

   Utilisé par : connexion_client.html, connexion_vendeur.html,
                 inscription_client.html, inscription_vendeur.html,
                 reinitialiser_mot_de_passe.html, registration/login.html

   API : window.ShopyPasswordToggle.init(element)  (formulaires AJAX)
   ============================================================ */
(function () {
  'use strict';

  var ICON_EYE =
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" ' +
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
    'stroke-linejoin="round" aria-hidden="true" focusable="false">' +
    '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>' +
    '<circle cx="12" cy="12" r="3"></circle></svg>';

  var ICON_EYE_OFF =
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" ' +
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
    'stroke-linejoin="round" aria-hidden="true" focusable="false">' +
    '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94' +
    'M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19' +
    'm-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>' +
    '<line x1="1" y1="1" x2="23" y2="23"></line></svg>';

  var LABEL_SHOW = 'Afficher le mot de passe';
  var LABEL_HIDE = 'Masquer le mot de passe';

  var SELECTOR = 'input[type="password"]';

  /* Met à jour l'icône et les libellés d'accessibilité du bouton */
  function refreshButton(button, visible) {
    button.innerHTML = visible ? ICON_EYE_OFF : ICON_EYE;
    button.setAttribute('aria-label', visible ? LABEL_HIDE : LABEL_SHOW);
    button.setAttribute('title', visible ? LABEL_HIDE : LABEL_SHOW);
    button.setAttribute('aria-pressed', visible ? 'true' : 'false');

    if (visible) {
      button.classList.add('is-visible');
    } else {
      button.classList.remove('is-visible');
    }
  }

  /* Bascule le mot de passe entre masqué (•••) et visible (texte) */
  function togglePassword(button, input) {
    var visible = input.getAttribute('type') === 'password';

    input.setAttribute('type', visible ? 'text' : 'password');
    refreshButton(button, visible);

    /* On garde le focus dans le champ, curseur en fin de saisie */
    try {
      input.focus();
      var end = input.value.length;
      input.setSelectionRange(end, end);
    } catch (err) {
      /* setSelectionRange() non supporté : on ignore */
    }
  }

  /* Enveloppe le champ et ajoute le bouton œil */
  function enhance(input) {
    if (!input || input.getAttribute('type') !== 'password') return;
    if (input.getAttribute('data-password-toggle') === 'on') return;

    var parent = input.parentNode;
    if (!parent) return;

    var wrapper = document.createElement('div');
    wrapper.className = 'password-field';

    parent.insertBefore(wrapper, input);
    wrapper.appendChild(input);

    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'password-toggle';
    if (input.id) {
      button.setAttribute('aria-controls', input.id);
    }
    refreshButton(button, false);

    button.addEventListener('click', function (event) {
      event.preventDefault();
      togglePassword(button, input);
    });

    wrapper.appendChild(button);
    input.setAttribute('data-password-toggle', 'on');
  }

  /* Equipe tous les champs mot de passe d'un conteneur (document par défaut) */
  function init(scope) {
    var root = scope || document;

    if (root.nodeType === 1 && root.matches && root.matches(SELECTOR)) {
      enhance(root);
      return;
    }

    if (!root.querySelectorAll) return;

    var fields = root.querySelectorAll(SELECTOR);
    for (var i = 0; i < fields.length; i += 1) {
      enhance(fields[i]);
    }
  }

  function ready() {
    init(document);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ready);
  } else {
    ready();
  }

  window.ShopyPasswordToggle = { init: init, refresh: ready };
})();
