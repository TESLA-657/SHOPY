/**
 * Notifications Polling Manager pour SHOPY
 * Vérifie les nouvelles notifications toutes les X secondes
 * Fonctionne sans Firebase
 */

const NotificationPolling = {
  // Configuration
  interval: 30000,  // 30 secondes
  timer: null,
  lastCheck: null,
  enabled: false,
  
  /**
   * Démarre le polling
   */
  start() {
    if (this.timer) return;  // Already running
    
    this.enabled = true;
    this.checkNow();  // Check immediately
    
    this.timer = setInterval(() => {
      this.checkNow();
    }, this.interval);
    
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
   * Affiche les nouvelles notifications comme toasts
   */
  afficherNotifications(notifications) {
    notifications.forEach((notif, index) => {
      setTimeout(() => {
        this.afficherToast(notif.titre, notif.message, notif.type);
      }, index * 500);  // Stagger les toasts
    });
  },
  
  /**
   * Affiche un toast de notification
   */
  afficherToast(titre, message, type) {
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
    toast.innerHTML = `
      <div class="toast-icon">${icon}</div>
      <div class="toast-content">
        <div class="toast-title">${titre}</div>
        <div class="toast-message">${message}</div>
      </div>
      <button class="toast-close" onclick="this.parentElement.remove()">×</button>
    `;
    
    container.appendChild(toast);
    
    // Auto-supprimer après 8 secondes
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
