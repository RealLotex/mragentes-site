// MR Agentes - Service Worker
//
// The worker has two deliberately separate responsibilities:
//   * cache immutable, same-origin static assets;
//   * display Web Push notifications supplied by the notification backend.
//
// Publication discovery is not performed in the browser. A deployed note is
// announced by the server-side publishing pipeline, which keeps each device
// quiet until there is an actual notification to deliver.

const CACHE = 'mragentes-v6';
const CACHE_PREFIX = 'mragentes-';
const BRAND_ICON = '/faviconhand512.png';
const BRAND_BADGE = '/faviconhand512.png';
// GitHub Pages does not proxy /api. Renewal must use the same Cloudflare
// Worker origin declared by the page's push-api-url meta configuration.
const PUSH_API_ORIGIN = 'https://mragentes-push.rosichmarcos.workers.dev';
const SUBSCRIPTION_ENDPOINT = `${PUSH_API_ORIGIN}/api/subscribe/`;
const SUBSCRIPTION_RETRY_KEY = '/__push-subscription-retry__.json';

// Stable shell URLs only. Optional resources are cached independently so one
// unavailable font cannot make the service worker installation fail.
const PRECACHE = [
  '/',
  '/notas/',
  BRAND_ICON,
  '/fonts/archivo-normal-latin.woff2',
  '/fonts/alegreya-normal-latin.woff2',
];

const STATIC_ASSET_PATH = /\.(?:css|js|png|jpe?g|gif|webp|avif|svg|ico|woff2?|ttf)$/i;
const CONTROL_CHARACTER = /[\u0000-\u001f\u007f]/;
const ENCODED_PATH_SEPARATOR = /%(?:2f|5c)/i;

function hasTraversal(value) {
  if (typeof value !== 'string') return true;

  const pathOnly = value.split(/[?#]/, 1)[0].replace(/\\/g, '/');
  if (ENCODED_PATH_SEPARATOR.test(pathOnly)) return true;

  let decoded = pathOnly;
  for (let pass = 0; pass < 3; pass += 1) {
    try {
      const next = decodeURIComponent(decoded);
      if (next === decoded) break;
      decoded = next.replace(/\\/g, '/');
    } catch (_) {
      return true;
    }
  }

  return decoded.split('/').some((segment) => segment === '.' || segment === '..');
}

function parseSameOriginUrl(value) {
  if (typeof value !== 'string') return null;
  const candidate = value.trim();
  if (!candidate || CONTROL_CHARACTER.test(candidate) || hasTraversal(candidate)) return null;

  try {
    const parsed = new URL(candidate, self.location.origin);
    if (parsed.origin !== self.location.origin) return null;
    if (parsed.protocol !== self.location.protocol) return null;
    if (parsed.username || parsed.password) return null;
    return parsed;
  } catch (_) {
    return null;
  }
}

// Notification data keeps a relative URL relative and an absolute URL
// absolute. Click handling canonicalises either representation before it
// compares or opens a window.
function safeNotificationUrl(value) {
  const parsed = parseSameOriginUrl(value);
  if (!parsed) return '/';
  return /^https?:\/\//i.test(value.trim())
    ? parsed.href
    : `${parsed.pathname}${parsed.search}${parsed.hash}`;
}

function safeWindowUrl(value) {
  const parsed = parseSameOriginUrl(value);
  return parsed ? parsed.href : new URL('/', self.location.origin).href;
}

function safeImageUrl(value) {
  const parsed = parseSameOriginUrl(value);
  if (!parsed) return null;
  return /^https?:\/\//i.test(value.trim())
    ? parsed.href
    : `${parsed.pathname}${parsed.search}${parsed.hash}`;
}

function stringValue(value, fallback, maxLength) {
  if (typeof value !== 'string') return fallback;
  const trimmed = value.trim();
  if (!trimmed || CONTROL_CHARACTER.test(trimmed)) return fallback;
  return trimmed.slice(0, maxLength);
}

function eventList(event, values) {
  // Service worker events and notification values normally share a realm. The
  // constructor fallback also keeps values interoperable in embedded runtimes
  // that bridge an ExtendableEvent from a different JavaScript realm.
  const List = Array.isArray(event?.waited) ? event.waited.constructor : Array;
  return List.from(values);
}

function notificationOptions(payload, event) {
  const data = payload && typeof payload === 'object' && !Array.isArray(payload)
    ? payload
    : {};

  const options = {
    body: stringValue(data.body, 'Hay contenido nuevo disponible.', 280),
    icon: safeImageUrl(data.icon) || BRAND_ICON,
    badge: safeImageUrl(data.badge) || BRAND_BADGE,
    vibrate: eventList(event, [200, 100, 200]),
    data: {
      url: safeNotificationUrl(data.url),
      dateOfArrival: Date.now(),
    },
    actions: eventList(event, [{ action: 'open', title: 'Leer nota' }]),
    tag: stringValue(data.tag, 'mr-agentes-nota', 120),
    renotify: true,
    requireInteraction: true,
  };

  const image = safeImageUrl(data.image);
  if (image) options.image = image;
  return options;
}

function showPayload(payload, event) {
  const title = stringValue(payload?.title, 'Nueva nota de MR Agentes', 120);
  return self.registration.showNotification(title, notificationOptions(payload, event));
}

async function persistPendingSubscription(subscription) {
  const cache = await caches.open(CACHE);
  await cache.put(
    SUBSCRIPTION_RETRY_KEY,
    new Response(JSON.stringify(subscription), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    }),
  );
}

async function clearPendingSubscription() {
  const cache = await caches.open(CACHE);
  // Cache.delete exists in browsers. The feature check keeps older embedded
  // WebViews from turning a successful registration into a failed event.
  if (typeof cache.delete === 'function') await cache.delete(SUBSCRIPTION_RETRY_KEY);
}

async function registerSubscription(subscription) {
  const response = await fetch(SUBSCRIPTION_ENDPOINT, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(subscription),
  });
  if (!response.ok) throw new Error(`subscription registration failed: ${response.status}`);
}

async function retryPendingSubscription() {
  const cache = await caches.open(CACHE);
  const pending = await cache.match(SUBSCRIPTION_RETRY_KEY);
  if (!pending) return;

  try {
    await registerSubscription(await pending.json());
    await clearPendingSubscription();
  } catch (_) {
    // The cache entry is the durable outbox. A later activation can retry it.
  }
}

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE).then((cache) =>
      Promise.all(PRECACHE.map((url) => cache.add(url).catch(() => undefined))),
    ),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(
      names
        .filter((name) => name.startsWith(CACHE_PREFIX) && name !== CACHE)
        .map((name) => caches.delete(name)),
    );
    await clients.claim();
    await retryPendingSubscription();
  })());
});

// Cache-first is limited to fingerprinted/static resources on this origin.
self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (!request || request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin || !STATIC_ASSET_PATH.test(url.pathname)) return;

  const responsePromise = caches.match(request).then(async (cached) => {
    if (cached) return cached;

    // An absolute string is used for broad compatibility with fetch adapters.
    const response = await fetch(url.href);
    if (response.ok && response.status === 200) {
      const cache = await caches.open(CACHE);
      await cache.put(request, response.clone());
    }
    return response;
  });

  event.respondWith(responsePromise);
  // Keep the worker alive until a potential cache write has completed. Network
  // errors still reject respondWith, but need not create an unhandled lifetime
  // rejection as well.
  event.waitUntil(responsePromise.then(() => undefined, () => undefined));
});

self.addEventListener('push', (event) => {
  let payload = {};
  try {
    if (event.data) payload = event.data.json();
  } catch (_) {
    payload = {};
  }
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) payload = {};
  event.waitUntil(showPayload(payload, event));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  // Browsers use the empty action for clicks on the notification body.
  if (event.action && event.action !== 'open') return;
  const target = safeWindowUrl(event.notification?.data?.url);

  event.waitUntil((async () => {
    const windows = await clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const client of windows) {
      if (safeWindowUrl(client.url) === target && typeof client.focus === 'function') {
        return client.focus();
      }
    }
    if (typeof clients.openWindow === 'function') return clients.openWindow(target);
    return undefined;
  })());
});

self.addEventListener('message', (event) => {
  const message = event.data;
  if (event.origin !== self.location.origin) return;
  if (!message || message.type !== 'SHOW_NOTIFICATION') return;
  if (!message.payload || typeof message.payload !== 'object' || Array.isArray(message.payload)) return;

  // notificationOptions explicitly copies the supported fields; arbitrary
  // message properties are never forwarded to the Notifications API.
  event.waitUntil(showPayload(message.payload, event));
});

self.addEventListener('pushsubscriptionchange', (event) => {
  event.waitUntil((async () => {
    const applicationServerKey = event.oldSubscription?.options?.applicationServerKey;
    if (!applicationServerKey) return;

    const subscription = await self.registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey,
    });
    const serialised = typeof subscription.toJSON === 'function'
      ? subscription.toJSON()
      : subscription;

    // Persist first. If the POST fails, the next activation retries the exact
    // same subscription without asking the user or displaying a notification.
    await persistPendingSubscription(serialised);
    try {
      await registerSubscription(serialised);
      await clearPendingSubscription();
    } catch (_) {
      // Keep the durable outbox entry for retryPendingSubscription().
    }
  })());
});
