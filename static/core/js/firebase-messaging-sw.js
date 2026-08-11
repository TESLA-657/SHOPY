/**
 * Service Worker pour Firebase Cloud Messaging
 * Gère les notifications push même quand l'app est fermée
 */

// Import Firebase scripts depuis le CDN
importScripts('https://www.gstatic.com/firebasejs/9.0.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/9.0.0/firebase-messaging-compat.js');

// Configuration Firebase - À remplacer par votre config Firebase Console
firebase.initializeApp({
  apiKey: "VOTRE_API_KEY",
  authDomain: "shopy-guinee.firebaseapp.com",
  projectId: "shopy-guinee",
  storageBucket: "shopy-guinee.appspot.com",
  messagingSenderId: "VOTRE_SENDER_ID",
  appId: "VOTRE_APP_ID"
});

const messaging = firebase.messaging();

// Gérer les messages en arrière-plan
messaging.onBackgroundMessage(function(payload) {
  console.log('[firebase-messaging-sw.js] Message reçu en arrière-plan:', payload);
  
  const notificationTitle = payload.notification.title || 'SHOPY';
  const notificationOptions = {
    body: payload.notification.body || 'Nouvelle notification',
    icon: '/static/core/images/shopy-logo.svg',
    badge: '/static/core/images/shopy-logo.svg',
    tag: 'shopy-notification',
    renotify: true,
    data: payload.data || {}
  };
  
  return self.registration.showNotification(notificationTitle, notificationOptions);
});

// Gérer le clic sur la notification
self.addEventListener('notificationclick', function(event) {
  console.log('[firebase-messaging-sw.js] Notification cliquée:', event.notification);
  event.notification.close();
  
  const data = event.notification.data || {};
  const url = data.url || '/';
  
  // Ouvrir l'URL si disponible
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then(function(clientList) {
        // Si une fenêtre est déjà ouverte,.focus celle-ci
        for (const client of clientList) {
          if (client.url === url && 'focus' in client) {
            return client.focus();
          }
        }
        // Sinon, ouvrir une nouvelle fenêtre
        return clients.openWindow(url);
      })
  );
});
