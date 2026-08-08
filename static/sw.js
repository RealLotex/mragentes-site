// MR Agentes — Service Worker v3
//
// Dos correcciones respecto de la versión anterior:
//
// 1. Precargaba /css/brand.css y /js/push-notifications.js por nombre fijo.
//    Ahora las hojas y los scripts llevan huella digital en el nombre
//    (main.min.<hash>.css), así que esas rutas ya no existen — y como addAll()
//    falla entero si una sola petición falla, el service worker no llegaba a
//    instalarse y los avisos dejaban de funcionar sin decir nada. Se precargan
//    sólo rutas estables, y una por una.
//
// 2. El manejador de fetch respondía desde el cache pero nunca guardaba nada,
//    así que el cache jamás se llenaba más allá de la precarga. Ahora guarda.
const CACHE = 'mragentes-v5';
const NOTA_LIST_URL = 'https://mragentes.com.ar/notas/index.json';

// Sólo rutas que no cambian de nombre entre publicaciones.
const PRECACHE = [
  '/',
  '/notas/',
  '/faviconhand512.png',
  '/fonts/archivo-normal-latin.woff2',
  '/fonts/alegreya-normal-latin.woff2',
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE).then((cache) =>
      // Una por una: que falte una fuente no debe impedir la instalación.
      Promise.all(PRECACHE.map((url) => cache.add(url).catch(() => {})))
    )
  );
});

self.addEventListener('activate', (event) => {
  console.log('[SW] Activado v2.1');
  event.waitUntil(
    (async () => {
      // Limpiar caches viejos
      const cacheNames = await caches.keys();
      await Promise.all(
        cacheNames.filter(name => name !== CACHE).map(name => {
          console.log('[SW] Eliminando cache viejo:', name);
          return caches.delete(name);
        })
      );
      await clients.claim();
      console.log('[SW] Clientes reclamados, cache actual:', CACHE);
      // Verificar contenido nuevo al activarse
      await checkForNewContent();
    })()
  );
});

// Cache-first para estáticos propios, guardando lo que se descarga.
// Es seguro servir desde cache indefinidamente porque los nombres llevan huella:
// cuando cambia el contenido cambia la URL, así que nunca se sirve algo viejo.
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (!/\.(css|js|png|jpg|jpeg|gif|svg|ico|woff2?|ttf)$/.test(url.pathname)) return;

  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req).then((res) => {
        // Sólo se guardan respuestas completas y correctas: guardar un 404 o una
        // respuesta parcial deja el error clavado hasta el próximo despliegue.
        if (res.ok && res.status === 200) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        }
        return res;
      });
    })
  );
});

// ─── Push Event ───────────────────────────────────────────────────────────
self.addEventListener('push', (event) => {
  console.log('[SW] Push recibido:', event.data ? 'con datos' : 'sin datos');

  let data = {};
  try {
    if (event.data) data = event.data.json();
  } catch (e) {
    console.warn('[SW] Push sin JSON válido, usando defaults');
    data = { title: 'MR Agentes' };
  }

  const title = data.title || 'Nueva nota de MR Agentes';
  const options = {
    body: data.body || 'Hay contenido nuevo disponible.',
    icon: '/images/notif-icon-white.png',
    badge: '/images/badge-icon-white.png',
    image: data.image || '/images/notif-image.png',
    vibrate: [200, 100, 200],
    data: { url: data.url || '/', dateOfArrival: Date.now() },
    actions: [
      { action: 'open', title: 'Leer nota' },
      { action: 'close', title: 'Cerrar' },
    ],
    tag: data.tag || 'new-nota',
    renotify: true,
    requireInteraction: true,
  };

  event.waitUntil(
    self.registration.showNotification(title, options).then(() => {
      console.log('[SW] Notificación mostrada:', title);
    }).catch((e) => {
      console.error('[SW] Error al mostrar notificación:', e);
    })
  );
});

// ─── Notification Click ───────────────────────────────────────────────────
self.addEventListener('notificationclick', (event) => {
  console.log('[SW] Click en notificación:', event.action);
  event.notification.close();
  if (event.action === 'close') return;

  const url = event.notification.data?.url || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clist) => {
      for (const c of clist) {
        if (c.url === url && 'focus' in c) {
          console.log('[SW] Ventana existente enfocada:', c.url);
          return c.focus();
        }
      }
      if (clients.openWindow) {
        console.log('[SW] Abriendo nueva ventana:', url);
        return clients.openWindow(url);
      }
    })
  );
});

// ─── Messages from client ─────────────────────────────────────────────────
self.addEventListener('message', (event) => {
  console.log('[SW] Mensaje del cliente:', event.data?.type);
  if (event.data && event.data.type === 'SHOW_NOTIFICATION') {
    const d = event.data.payload;
    self.registration.showNotification(d.title || 'MR Agentes', {
      body: d.body || '',
      icon: '/images/notif-icon-white.png',
      badge: '/images/badge-icon-white.png',
      data: { url: d.url || '/' },
      actions: [
        { action: 'open', title: 'Leer nota' },
        { action: 'close', title: 'Cerrar' },
      ],
    });
  }
});

// ─── Check for new content ────────────────────────────────────────────────
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
      console.log('[SW] Nueva nota detectada:', latest.title);
      const allClients = await self.clients.matchAll();
      allClients.forEach((client) => {
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
