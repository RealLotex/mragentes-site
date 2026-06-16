// MR Agentes — Service Worker v2.0
const CACHE = 'mragentes-v3';
const LAST_NEWS_KEY = 'mragentes-last-nota';
const NOTA_LIST_URL = 'https://mragentes.com.ar/notas/index.json';

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE).then((cache) => {
      return cache.addAll([
        '/',
        '/css/brand.css',
        '/css/scroll.css',
        '/js/scroll-animations.js',
        '/js/push-notifications.js',
      ]);
    })
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      await clients.claim();
      // Verificar contenido nuevo al activarse (después de un deploy)
      await checkForNewContent();
    })()
  );
});

// Cache-first para assets estáticos
self.addEventListener('fetch', (event) => {
  // Solo cachear assets estáticos, no páginas
  if (event.request.url.match(/\.(css|js|png|jpg|jpeg|gif|svg|ico|woff2?|ttf)$/)) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        return cached || fetch(event.request);
      })
    );
  }
});

// Periodically check for new content (cada 30 min si está abierto)
self.addEventListener('periodicsync', (event) => {
  if (event.tag === 'check-notas') {
    event.waitUntil(checkForNewContent());
  }
});

// Manejar push events (cuando alguien nos envía un push real por web-push)
self.addEventListener('push', (event) => {
  let data = {};
  try {
    if (event.data) data = event.data.json();
  } catch (e) {
    data = { title: 'MR Agentes' };
  }

  const title = data.title || 'Nueva nota de MR Agentes';
  const options = {
    body: data.body || 'Hay contenido nuevo disponible.',
    icon: '/images/favicon.png',
    badge: '/images/favicon.png',
    image: data.image,
    vibrate: [200, 100, 200],
    data: { url: data.url || '/', dateOfArrival: Date.now() },
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
  const url = event.notification.data?.url || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clist) => {
      for (const c of clist) {
        if (c.url === url && 'focus' in c) return c.focus();
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});

// ** Mensajes desde el cliente **
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SHOW_NOTIFICATION') {
    const d = event.data.payload;
    self.registration.showNotification(d.title || 'MR Agentes', {
      body: d.body || '',
      icon: '/images/favicon.png',
      badge: '/images/favicon.png',
      data: { url: d.url || '/' },
      actions: [
        { action: 'open', title: 'Leer nota' },
        { action: 'close', title: 'Cerrar' },
      ],
    });
  }
});

async function checkForNewContent() {
  try {
    const resp = await fetch(NOTA_LIST_URL, { cache: 'no-store' });
    if (!resp.ok) return;
    const notas = await resp.json();
    if (!notas || notas.length === 0) return;

    const latest = notas[notas.length - 1];
    const cache = await caches.open(CACHE);
    const cachedResp = await cache.match(NOTA_LIST_URL);
    let lastTitle = '';

    if (cachedResp) {
      try {
        const cachedData = await cachedResp.json();
        if (cachedData.length > 0) {
          lastTitle = cachedData[cachedData.length - 1]?.title || '';
        }
      } catch (e) {}
    }

    if (latest.title && latest.title !== lastTitle) {
      // Nueva nota detectada!
      const clients = await self.clients.matchAll();
      clients.forEach((client) => {
        client.postMessage({ type: 'NEW_NOTA', payload: latest });
      });
    }

    // Actualizar cache
    const clonedResp = resp.clone();
    const cacheToStore = await caches.open(CACHE);
    cacheToStore.put(NOTA_LIST_URL, clonedResp);

    return latest;
  } catch (e) {
    console.error('[SW] Error checking new content:', e);
  }
}
