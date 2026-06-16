// MR Agentes — Service Worker v1.0
const CACHE = 'mragentes-v1';
const API_URL = 'https://mragentes.com.ar/';

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE).then((cache) => {
      return cache.addAll([
        '/',
        '/css/brand.css',
        '/css/scroll.css',
        '/js/scroll-animations.js',
      ]);
    })
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(clients.claim());
});

// Cache-first para assets estáticos
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((cached) => {
      return cached || fetch(event.request);
    })
  );
});

// === NOTIFICACIONES PUSH ===

self.addEventListener('push', (event) => {
  let data = {};
  try {
    if (event.data) {
      data = event.data.json();
    }
  } catch (e) {
    data = { title: 'MR Agentes' };
  }

  const title = data.title || 'Nueva nota de MR Agentes';
  const options = {
    body: data.body || 'Hay contenido nuevo disponible.',
    icon: data.icon || '/images/favicon.png',
    badge: '/images/favicon.png',
    image: data.image,
    vibrate: [200, 100, 200],
    data: {
      url: data.url || '/',
      dateOfArrival: Date.now(),
    },
    actions: [
      { action: 'open', title: 'Leer nota' },
      { action: 'close', title: 'Cerrar' },
    ],
    tag: data.tag || 'new-nota',
    renotify: true,
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  if (event.action === 'close') return;

  const urlToOpen = event.notification.data?.url || '/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url === urlToOpen && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(urlToOpen);
      }
    })
  );
});
