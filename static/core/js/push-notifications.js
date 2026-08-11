/**
 * Push Notifications Manager pour SHOPY
 * Gère l'inscription aux notifications push Firebase
 */

const PushNotifications = {
  // Configuration Firebase - À configurer dans Firebase Console
  firebaseConfig: {
    apiKey: "VOTRE_API_KEY",
    authDomain: "shopy-guinee.firebaseapp.com",
    projectId: "shopy-guinee",
    storageBucket: "shopy-guinee.appspot.com",
    messagingSenderId: "VOTRE_SENDER_ID",
    appId: "VOTRE_APP_ID"
  },
  
  messaging: null,
  token: null,
  initialized: false,
  
  /**
   * Initialise Firebase et le service de messaging
   */
  async init() {
    if (this.initialized) return;
    
    // Vérifier si Firebase est déjà chargé
    if (typeof firebase === 'undefined') {
      console.warn('Push: Firebase non chargé');
      return;
    }
    
    try {
      // Initialiser Firebase
      if (!firebase.apps.length) {
        firebase.initializeApp(this.firebaseConfig);
      }
      
      this.messaging = firebase.messaging();
      this.initialized = true;
      console.log('Push: Initialisé');
    } catch (e) {
      console.error('Push: Erreur初始化:', e);
    }
  },
  
  /**
   * Demande la permission de notifications
   */
  async requestPermission() {
    try {
      const permission = await Notification.requestPermission();
      
      if (permission === 'granted') {
        console.log('Push: Permission accordée');
        await this.init();
        return true;
      } else if (permission === 'denied') {
        console.warn('Push: Permission refusée');
        this.afficherPopup('🔕', 'Notifications bloquées', 
          'Veuillez autoriser les notifications dans les paramètres du navigateur.');
        return false;
      } else {
        console.log('Push: Permission ignorée');
        return false;
      }
    } catch (e) {
      console.error('Push: Erreur permission:', e);
      return false;
    }
  },
  
  /**
   * Obtient le token FCM et l'enregistre sur le serveur
   */
  async getToken() {
    if (!this.messaging) {
      await this.init();
    }
    
    if (!this.messaging) {
      console.warn('Push: Messaging non disponible');
      return null;
    }
    
    try {
      // Obtenir le token
      const token = await this.messaging.getToken({
        vapidKey: "VOTRE_VAPID_KEY" // Générer depuis Firebase Console
      });
      
      this.token = token;
      console.log('Push: Token obtenu:', token.substring(0, 20) + '...');
      
      // Envoyer au serveur
      await this.enregistrerToken(token);
      
      return token;
    } catch (e) {
      console.error('Push: Erreur getToken:', e);
      return null;
    }
  },
  
  /**
   * Enregistre le token sur le serveur
   */
  async enregistrerToken(token) {
    try {
      const response = await fetch('/api/enregistrer-token/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.getCSRFToken()
        },
        body: JSON.stringify({
          fcm_token: token,
          device_type: this.getDeviceType()
        })
      });
      
      const data = await response.json();
      console.log('Push: Token enregistré:', data);
      return data;
    } catch (e) {
      console.error('Push: Erreur enregistrement:', e);
      return null;
    }
  },
  
  /**
   * Supprime le token du serveur
   */
  async supprimerToken() {
    if (!this.token) return;
    
    try {
      const response = await fetch('/api/supprimer-token/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.getCSRFToken()
        },
        body: JSON.stringify({
          fcm_token: this.token
        })
      });
      
      this.token = null;
      console.log('Push: Token supprimé');
      return true;
    } catch (e) {
      console.error('Push: Erreur suppression:', e);
      return false;
    }
  },
  
  /**
   * Écoute les messages foreground
   */
  onMessage() {
    if (!this.messaging) return;
    
    this.messaging.onMessage((payload) => {
      console.log('Push: Message reçu:', payload);
      
      const titre = payload.notification.title || 'SHOPY';
      const body = payload.notification.body || '';
      
      // Afficher le toast
      if (typeof window.afficherToast === 'function') {
        window.afficherToast(titre, body);
      } else {
        this.afficherToastSimple(titre, body);
      }
    });
  },
  
  /**
   * Affiche un toast simple
   */
  afficherToastSimple(titre, message) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = 'toast-item';
    toast.innerHTML = `
      <div class="toast-icon">🔔</div>
      <div class="toast-content">
        <div class="toast-title">${titre}</div>
        <div class="toast-message">${message}</div>
      </div>
    `;
    
    container.appendChild(toast);
    
    // Auto-supprimer après 5 secondes
    setTimeout(() => {
      toast.remove();
    }, 5000);
  },
  
  /**
   * Affiche un popup
   */
  afficherPopup(icon, titre, message) {
    if (typeof window.afficherPopup === 'function') {
      window.afficherPopup(icon, titre, message);
    } else {
      alert(titre + '\n' + message);
    }
  },
  
  /**
   * Détecte le type d'appareil
   */
  getDeviceType() {
    const ua = navigator.userAgent.toLowerCase();
    if (/ipad|iphone|ipod/.test(ua)) return 'ios';
    if (/android/.test(ua)) return 'android';
    return 'web';
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
  },
  
  /**
   * Active les notifications push
   */
  async activer() {
    const aPermission = await this.requestPermission();
    if (aPermission) {
      await this.getToken();
      this.onMessage();
      this.afficherPopup('✅', 'Notifications activées', 
        'Vous recevrez des notifications pour vos commandes et messages.');
      return true;
    }
    return false;
  },
  
  /**
   * Désactive les notifications push
   */
  async desactiver() {
    await this.supprimerToken();
    
    if (this.messaging) {
      try {
        await this.messaging.deleteToken();
      } catch (e) {
        console.log('Push: Token déjà supprimé');
      }
    }
    
    this.afficherPopup('🔕', 'Notifications désactivées', 
      'Vous ne recevrez plus de notifications push.');
  }
};

// Auto-init quand le DOM est prêt
document.addEventListener('DOMContentLoaded', function() {
  // Vérifier si l'utilisateur est connecté
  const isAuthenticated = document.body.getAttribute('data-authenticated') === 'true';
  
  if (isAuthenticated) {
    PushNotifications.init().then(() => {
      // Demander permission automatiquement si pas encore
      if (Notification.permission === 'default') {
        // Ne pas demander automatiquement, laisser l'utilisateur choisir
        console.log('Push: Prêt - affichez un bouton pour activer');
      } else if (Notification.permission === 'granted') {
        PushNotifications.getToken();
        PushNotifications.onMessage();
      }
    });
  }
});

// Fonctions globales pour les boutons
window.activerNotifications = function() {
  return PushNotifications.activer();
};

window.desactiverNotifications = function() {
  return PushNotifications.desactiver();
};

// Export pour usage externe
if (typeof module !== 'undefined' && module.exports) {
  module.exports = PushNotifications;
}
