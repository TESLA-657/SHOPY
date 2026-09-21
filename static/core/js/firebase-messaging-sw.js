/**
 * Service Worker pour Firebase Cloud Messaging
 * Gère les notifications push même quand l'app est fermée
 */

// Import Firebase scripts depuis le CDN
importScripts('https://www.gstatic.com/firebasejs/9.0.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/9.0.0/firebase-messaging-compat.js');

// Fiabiliser FCM (clés injectées via template Django depuis settings)
firebase.initializeApp({
  apiKey: FIREBASE_API_KEY,
  authDomain: FIREBASE_AUTH_DOMAIN,
  projectId: FIREBASE_PROJECT_ID,
  storageBucket: FIREBASE_STORAGE_BUCKET,
  messagingSenderId: FIREBASE_SENDER_ID,
  appId: FIREBASE_APP_ID
});

const messaging = firebase.messaging();

// Callback pour autorisation
messaging.requestPermission().then(() => {
  console.log('Notification permission granted.');
  return messaging.getToken();
}).then((token) => {
  console.log('FCM Token:', token);
  // Envoyer le token au serveur via API
  if (window.sendFcmToken) {
    window.sendFcmToken(token);
  }
}).catch((error) => {
  console.error('Notification permission denied:', error);
});

// Gérer les messages en arrière-plan
messaging.onBackgroundMessage(function(payload) {
  console.log('[firebase-messaging-sw.js] Message reçu:', payload);
  
  const notificationTitle = payload.notification?.title || 'SHOPY';
  const notificationBody = payload.notification?.body || 'Nouvelle notification';
  
  const notificationOptions = {
    body: notificationBody,
    icon: '/static/core/images/log.png',
    badge: '/static/core/images/log.png',
    tag: 'shopy-notification',
    renotify: true,
    data: payload.data || {}
  };
  
  return self.registration.showNotification(notificationTitle, notificationOptions);
});

// Gérer le clic sur la notification
self.addEventListener('notificationclick', function(event) {
  console.log('[firebase-messaging-sw.js] Notification cliquée');
  event.notification.close();
  
  const data = event.notification.data || {};
  const url = data.url || '/';
  
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then(function(clientList) {
        for (const client of clientList) {
          if (client.url === url && 'focus' in client) {
            return client.focus();
          }
        }
        return clients.openWindow(url);
      })
  );
});
