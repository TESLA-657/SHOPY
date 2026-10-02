/**
 * Notifications Polling Manager pour SHOPY
 * Vérifie les nouvelles notifications toutes les X secondes
 * Fonctionne sans Firebase
 */

const NotificationPolling = {
  // Configuration
  // 30 secondes etait trop agressif : avec 1000 vendeurs connectes
  // cela representait ~33 requetes/seconde permanentes pour rien.
  // 2 minutes divise la charge par 4, sans perte utile : une
  // notification de commande n'a pas besoin d'arriver en 5 secondes.
  interval: 120000,  // 2 minutes
  timer: null,
  lastCheck: null,
  enabled: false,

  /**
   * Le polling ne doit tourner que si l'onglet est visible.
   * Un onglet en arriere-plan n'affiche rien : inutile de
   * interroger le serveur toutes les 2 minutes pour rien.
   */
  ongletVisible() {
    return document.visibilityState === 'visible';
  },

  /**
   * Démarre le polling
   */
  start() {
    if (this.timer) return;  // Already running

    this.enabled = true;
    if (this.ongletVisible()) this.checkNow();

    this.timer = setInterval(() => {
      if (!this.ongletVisible()) return;  // onglet en arriere-plan
      this.checkNow();
    }, this.interval);

    // Reprise immediate quand l'utilisateur revient sur l'onglet :
    // on ne veut pas attendre 2 minutes apres un retour sur le site.
    document.addEventListener('visibilitychange', () => {
      if (this.ongletVisible() && this.enabled) this.checkNow();
    });

    console.log('NotificationPolling: Démarré');
  },
  
  /**
   * Arrête le polling
   */
  stop() {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    this.enabled = false;
    console.log('NotificationPolling: Arrêté');
  },
  
  /**
   * Vérifie les nouvelles notifications maintenant
   */
  async checkNow() {
    try {
      const response = await fetch('/api/notifications/nouvelles/', {
        headers: {
          'X-CSRFToken': this.getCSRFToken()
        }
      });
      
      const data = await response.json();
      
      if (data.nouvelles && data.nouvelles.length > 0) {
        this.afficherNotifications(data.nouvelles);
      }
      
      // Mettre à jour le badge
      this.updateBadge(data.nb_non_lues);
      
    } catch (e) {
      console.error('NotificationPolling: Erreur:', e);
    }
  },
  
  /**
   * Marque une notification comme lue en base (croix de fermeture).
   * Indispensable : sans appel serveur, la notification est renvoyee
   * au prochain chargement de page et reapparait au polling suivant.
   */
  marquerCommeLue(id) {
    if (!id) return;
    fetch(`/api/notifications/${id}/marquer-lue/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': this.getCSRFToken() },
      credentials: 'same-origin'
    }).then(r => r.json())
      .then(data => this.updateBadge(data && data.nb_non_lues))
      .catch(() => {});
  },

  /**
   * Memorise localement les notifications fermees par l'utilisateur,
   * afin qu'elles ne reapparaissent pas au prochain chargement de page.
   */
  memoriserFermee(id) {
    if (!id) return;
    try {
      const key = 'shopy_notif_lues';
      const list = JSON.parse(localStorage.getItem(key) || '[]');
      if (!list.includes(id)) {
        list.push(id);
        localStorage.setItem(key, JSON.stringify(list.slice(-100)));
      }
    } catch (e) { /* stockage indisponible : la base reste la reference */ }
  },

  dejaFermees() {
    try {
      return JSON.parse(localStorage.getItem('shopy_notif_lues') || '[]');
    } catch (e) { return []; }
  },

  /**
   * Affiche les nouvelles notifications comme toasts
   */
  afficherNotifications(notifications) {
    const fermees = this.dejaFermees();
    notifications.forEach((notif, index) => {
      // Ne pas re-afficher une notification deja fermee par l'utilisateur.
      if (notif.id != null && fermees.includes(notif.id)) return;
      setTimeout(() => {
        this.afficherToast(notif.titre, notif.message, notif.type, notif.id);
      }, index * 500);  // Stagger les toasts
    });
  },
  
  /**
   * Affiche un toast de notification
   */
  afficherToast(titre, message, type, id = null) {
    const container = document.getElementById('toast-container');
    if (!container) {
      console.warn('Toast container non trouvé');
      return;
    }
    
    // Icône selon le type
    const icones = {
      'commande': '🛒',
      'abonnement': '💳',
      'message': '💬',
      'securite': '🔒',
      'systeme': '⚙️'
    };
    
    const icon = icones[type] || '🔔';
    
    const toast = document.createElement('div');
    toast.className = 'toast-item toast-notification';

    // Construction via DOM au lieu de innerHTML : le titre et le message
    // viennent de la base et ne doivent jamais etre interpretes comme du HTML.
    const iconEl = document.createElement('div');
    iconEl.className = 'toast-icon';
    iconEl.textContent = icon;

    const contentEl = document.createElement('div');
    contentEl.className = 'toast-content';

    const titleEl = document.createElement('div');
    titleEl.className = 'toast-title';
    titleEl.textContent = titre;

    const msgEl = document.createElement('div');
    msgEl.className = 'toast-message';
    msgEl.textContent = message;

    contentEl.appendChild(titleEl);
    contentEl.appendChild(msgEl);

    const closeBtn = document.createElement('button');
    closeBtn.className = 'toast-close';
    closeBtn.textContent = '×';
    closeBtn.setAttribute('aria-label', 'Fermer la notification');

    toast.appendChild(iconEl);
    toast.appendChild(contentEl);
    toast.appendChild(closeBtn);

    // La croix marque la notification comme lue en base ET la
    // memorise localement : sans cela, elle reapparait au prochain
    // chargement de page et a chaque cycle de polling.
    closeBtn.addEventListener('click', () => {
      this.marquerCommeLue(id);
      this.memoriserFermee(id);
      toast.remove();
    });

    container.appendChild(toast);
    // force reflow for animation
    requestAnimationFrame(() => toast.classList.add('show'));

    // Auto-supprimer apres 8 secondes SANS marquer comme lue :
    // une simple disparition visuelle ne doit pas perdre la
    // notification (elle reste consultable dans la page Notifications).
    setTimeout(() => {
      if (toast.parentElement) {
        toast.remove();
      }
    }, 8000);
  },
  
  /**
   * Met à jour le badge de notifications
   */
  updateBadge(count) {
    const badge = document.querySelector('.notif-fab-badge');
    const link = document.querySelector('.notif-fab');
    
    if (badge) {
      if (count > 0) {
        badge.textContent = count;
        badge.style.display = 'flex';
      } else {
        badge.style.display = 'none';
      }
    }
    
    // Update document title si minimisé
    if (count > 0 && !document.hasFocus()) {
      document.title = `(${count}) 🔔 SHOPY`;
    } else {
      document.title = 'SHOPY';
    }
  },
  
  /**
   * Obtient le CSRF token
   */
  getCSRFToken() {
    const name = 'csrftoken';
    let cookieValue = null;
    
    if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    
    return cookieValue;
  }
};

// Auto-start quand le DOM est prêt (si utilisateur connecté)
document.addEventListener('DOMContentLoaded', function() {
  // Vérifier si l'utilisateur est connecté
  const isAuthenticated = document.body.getAttribute('data-authenticated') === 'true';
  
  if (isAuthenticated) {
    NotificationPolling.start();
  }
});

// Fonction globale pour afficher les paramètres
window.demarrerNotifications = function() {
  NotificationPolling.start();
};

window.arreterNotifications = function() {
  NotificationPolling.stop();
};

// Export
if (typeof module !== 'undefined' && module.exports) {
  module.exports = NotificationPolling;
}
