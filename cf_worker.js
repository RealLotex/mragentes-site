// MR Agentes — Cloudflare Worker for Web Push Notifications
// Deploy: wrangler deploy cf_worker.js --name mragentes-push
// Secrets (set via `wrangler secret put <NAME>`):
//   VAPID_PUBLIC_KEY   — VAPID public key (exposed to frontend)
//   VAPID_PRIVATE_KEY  — VAPID private key (keep secret!)
//   API_TOKEN          — Auth token for /api/send/
// KV Namespace Binding: PUSH_SUBS (configured in Cloudflare dashboard)
//
// API endpoints:
//   POST /api/subscribe/    — Save a push subscription
//   POST /api/unsubscribe/  — Remove a push subscription
//   POST /api/send/         — Send a push notification to all subscribers

const encoder = new TextEncoder();
const SITE_ORIGIN = 'https://mragentes.com.ar';
const BRAND_ICON = '/faviconhand512.png';
const BRAND_BADGE = '/faviconhand512.png';

function tokenOk(provided, expected) {
  if (typeof provided !== 'string' || typeof expected !== 'string' || provided.length !== expected.length) return false;
  let difference = 0;
  for (let i = 0; i < expected.length; i++) difference |= provided.charCodeAt(i) ^ expected.charCodeAt(i);
  return difference === 0;
}

function forbidden(cors) {
  return new Response(JSON.stringify({ error: 'Invalid token' }), {
    status: 403,
    headers: { ...cors, 'Content-Type': 'application/json' },
  });
}

function publicPostImage(value) {
  if (typeof value !== 'string' || !value.trim()) return null;
  try {
    const image = new URL(value, SITE_ORIGIN);
    if (image.origin !== SITE_ORIGIN || !image.pathname.startsWith('/images/stock/')) return null;
    return `${SITE_ORIGIN}${image.pathname}${image.search}`;
  } catch {
    return null;
  }
}

function buildNotificationPayload({ title, body, url, image, tag } = {}) {
  const payload = {
    title: String(title || 'MR Agentes').slice(0, 120),
    body: String(body || 'Hay contenido nuevo disponible.').slice(0, 255),
    url: typeof url === 'string' ? url.slice(0, 500) : `${SITE_ORIGIN}/`,
    icon: BRAND_ICON,
    badge: BRAND_BADGE,
    tag: String(tag || `nota-${Date.now()}`).slice(0, 120),
  };
  const postImage = publicPostImage(image);
  if (postImage) payload.image = postImage;
  return payload;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;
    const cors = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: cors });
    }

    try {
      if (path === '/api/subscribe/' && request.method === 'POST') {
        return await handleSubscribe(request, env, cors);
      }
      if (path === '/api/unsubscribe/' && request.method === 'POST') {
        return await handleUnsubscribe(request, env, cors);
      }
      if (path === '/api/send/' && request.method === 'POST') {
        return await handleSend(request, env, cors);
      }
      if (path === '/api/send/one/' && request.method === 'POST') {
        return await handleSendOne(request, env, cors);
      }
      if (path === '/api/debug/status' && request.method === 'GET') {
        return await handleDebugStatus(request, env, cors);
      }
      if (path === '/api/debug/clear-all' && request.method === 'POST') {
        return await handleClearAll(request, env, cors);
      }
      return new Response(JSON.stringify({ error: 'Not found' }), {
        status: 404,
        headers: { ...cors, 'Content-Type': 'application/json' },
      });
    } catch (e) {
      return new Response(JSON.stringify({ error: e.message }), {
        status: 500,
        headers: { ...cors, 'Content-Type': 'application/json' },
      });
    }
  },
};

// ─── Subscribe ───────────────────────────────────────────────────────────────

async function handleSubscribe(request, env, cors) {
  const body = await request.json();

  if (!body.endpoint || !body.keys || !body.keys.p256dh || !body.keys.auth) {
    return new Response(JSON.stringify({ error: 'Invalid subscription: endpoint, keys.p256dh, keys.auth required' }), {
      status: 400,
      headers: { ...cors, 'Content-Type': 'application/json' },
    });
  }

  // Validate endpoint URL
  try {
    new URL(body.endpoint);
  } catch {
    return new Response(JSON.stringify({ error: 'Invalid endpoint URL' }), {
      status: 400,
      headers: { ...cors, 'Content-Type': 'application/json' },
    });
  }

  // Store subscription, expires in 365 days
  await env.PUSH_SUBS.put(body.endpoint, JSON.stringify(body), {
    expirationTtl: 86400 * 365,
  });

  // Send welcome notification (fire-and-forget)
  sendWelcomePush(body, env).catch(e => console.error('Welcome push error:', e.message));

  return new Response(JSON.stringify({ status: 'ok' }), {
    status: 200,
    headers: { ...cors, 'Content-Type': 'application/json' },
  });
}

// ─── Welcome push on subscribe ─────────────────────────────────────────────

async function sendWelcomePush(sub, env) {
  const payload = JSON.stringify(buildNotificationPayload({
    title: '🔔 Bienvenido a MR Agentes',
    body: 'Activaste las notificaciones. Ahora vas a recibir alertas cuando publiquemos una nota nueva.',
    url: `${SITE_ORIGIN}/`,
    tag: 'welcome-' + Date.now(),
  }));

  const vapidHeaders = await generateVapidHeaders(
    sub.endpoint,
    'mailto:marcos@mragentes.com.ar',
    env.VAPID_PRIVATE_KEY,
    env.VAPID_PUBLIC_KEY,
  );
  const encrypted = await webPushEncrypt(
    payload,
    sub.keys.p256dh,
    sub.keys.auth,
  );

  const res = await fetch(sub.endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/octet-stream',
      'Content-Encoding': 'aes128gcm',
      TTL: '86400',
      Urgency: 'high',
      ...vapidHeaders,
    },
    body: encrypted,
  });

  if (!res.ok) {
    const text = await res.text();
    console.error('Welcome push failed:', res.status, text.slice(0, 200));
  }
}

// ─── Unsubscribe ─────────────────────────────────────────────────────────────

async function handleUnsubscribe(request, env, cors) {
  const body = await request.json();

  if (!body.endpoint) {
    return new Response(JSON.stringify({ error: 'Missing endpoint' }), {
      status: 400,
      headers: { ...cors, 'Content-Type': 'application/json' },
    });
  }

  await env.PUSH_SUBS.delete(body.endpoint);

  return new Response(JSON.stringify({ status: 'ok' }), {
    status: 200,
    headers: { ...cors, 'Content-Type': 'application/json' },
  });
}

// ─── Send to One Subscription (for debugging) ────────────────────────────

async function handleSendOne(request, env, cors) {
  const body = await request.json();
  if (!tokenOk(body.token, env.API_TOKEN)) return forbidden(cors);

  if (!body.subscription || !body.subscription.endpoint) {
    return new Response(JSON.stringify({ error: 'subscription.endpoint required' }), {
      status: 400,
      headers: { ...cors, 'Content-Type': 'application/json' },
    });
  }

  const sub = body.subscription;
  const title = (body.title || 'MR Agentes').slice(0, 120);
  const msgBody = (body.body || 'Test push').slice(0, 255);
  const url = body.url && typeof body.url === 'string' ? body.url.slice(0, 500) : 'https://mragentes.com.ar/';

  const payload = JSON.stringify(buildNotificationPayload({
    title,
    body: msgBody,
    url,
    image: body.image,
    tag: `debug-${Date.now()}`,
  }));

  try {
    const vapidHeaders = await generateVapidHeaders(
      sub.endpoint,
      'mailto:marcos@mragentes.com.ar',
      env.VAPID_PRIVATE_KEY,
      env.VAPID_PUBLIC_KEY,
    );
    const encrypted = await webPushEncrypt(
      payload,
      sub.keys.p256dh,
      sub.keys.auth,
    );

    const res = await fetch(sub.endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/octet-stream',
        'Content-Encoding': 'aes128gcm',
        TTL: '86400',
        Urgency: 'high',
        ...vapidHeaders,
      },
      body: encrypted,
    });

    const responseBody = await res.text();
    console.log(`Push one: ${res.status} for ${sub.endpoint.slice(0, 60)}: ${responseBody}`);

    return new Response(JSON.stringify({
      status: res.ok ? 'sent' : 'failed',
      status_code: res.status,
      response: responseBody.slice(0, 500),
      headers: Object.fromEntries(res.headers.entries()),
    }), {
      status: 200,
      headers: { ...cors, 'Content-Type': 'application/json' },
    });
  } catch (e) {
    return new Response(JSON.stringify({
      status: 'error',
      error: e.message,
    }), {
      status: 200,
      headers: { ...cors, 'Content-Type': 'application/json' },
    });
  }
}

// ─── Send Notification ───────────────────────────────────────────────────────

async function handleSend(request, env, cors) {
  const body = await request.json();
  if (!tokenOk(body.token, env.API_TOKEN)) return forbidden(cors);

  // Validate payload
  const title = (body.title || 'MR Agentes').slice(0, 120);
  const msgBody = (body.body || '').slice(0, 255);
  const url = body.url && typeof body.url === 'string' ? body.url.slice(0, 500) : 'https://mragentes.com.ar/';

  if (!msgBody) {
    return new Response(JSON.stringify({ error: 'body is required' }), {
      status: 400,
      headers: { ...cors, 'Content-Type': 'application/json' },
    });
  }

  const payload = JSON.stringify(buildNotificationPayload({
    title,
    body: msgBody,
    url,
    image: body.image,
    tag: `nota-${Date.now()}`,
  }));

  // Collect error details per subscription for debugging
  const errors = [];

  // Iterate all subscriptions via KV list
  let sent = 0;
  let failed = 0;
  let removed = 0;
  const BATCH_SIZE = 50;
  let cursor;
  let done = false;

  do {
    const listResult = await env.PUSH_SUBS.list({ cursor, limit: BATCH_SIZE });
    done = listResult.list_complete;
    cursor = listResult.cursor;

    const batch = listResult.keys;

    const results = await limitedConcurrency(batch, 10, async (key) => {
      try {
        const raw = await env.PUSH_SUBS.get(key.name);
        if (!raw) return null;

        const sub = JSON.parse(raw);
        if (!sub.keys || !sub.keys.p256dh || !sub.keys.auth) {
          await env.PUSH_SUBS.delete(key.name);
          removed++;
          return null;
        }

        const vapidHeaders = await generateVapidHeaders(
          sub.endpoint,
          'mailto:marcos@mragentes.com.ar',
          env.VAPID_PRIVATE_KEY,
          env.VAPID_PUBLIC_KEY,
        );
        const encrypted = await webPushEncrypt(
          payload,
          sub.keys.p256dh,
          sub.keys.auth,
        );

        const res = await fetch(sub.endpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/octet-stream',
            'Content-Encoding': 'aes128gcm',
            TTL: '86400',
            Urgency: 'high',
            ...vapidHeaders,
          },
          body: encrypted,
        });

        if (res.ok) {
          return 'sent';
        } else if (res.status === 410 || res.status === 404) {
          // Subscription expired/unregistered — key mismatch or unsubscribed
          const errText = await res.text();
          console.error(`Push 410/404 for ${sub.endpoint.slice(0, 60)}…: ${errText}`);
          await env.PUSH_SUBS.delete(key.name);
          removed++;
          if (errors.length < 3) {
            errors.push({ endpoint: sub.endpoint.slice(0, 60) + '…', status: res.status, detail: errText.slice(0, 200) });
          }
          return 'removed';
        } else {
          const errText = await res.text();
          console.error(`Push failed (${res.status}) for ${sub.endpoint.slice(0, 60)}…: ${errText}`);
          if (errors.length < 3) {
            errors.push({ endpoint: sub.endpoint.slice(0, 60) + '…', status: res.status, detail: errText.slice(0, 200) });
          }
          return 'failed';
        }
      } catch (e) {
        console.error('Send error:', e.message);
        if (errors.length < 3) {
          errors.push({ endpoint: 'unknown', error: e.message });
        }
        return 'failed';
      }
    });

    for (const r of results) {
      if (r === 'sent') sent++;
      else if (r === 'failed') failed++;
    }
  } while (!done);

  return new Response(
    JSON.stringify({ status: 'ok', sent, failed, removed, errors: errors.length > 0 ? errors : undefined }),
    { status: 200, headers: { ...cors, 'Content-Type': 'application/json' } },
  );
}

// ─── Debug: check status ────────────────────────────────────────────────────

async function handleDebugStatus(request, env, cors) {
  // Check that secrets are set
  const hasVapidPub = !!env.VAPID_PUBLIC_KEY;
  const hasVapidPriv = !!env.VAPID_PRIVATE_KEY;
  const hasApiToken = !!env.API_TOKEN;

  // Count subscriptions
  let subCount = 0;
  try {
    const listResult = await env.PUSH_SUBS.list({ limit: 1 });
    subCount = listResult.keys.length > 0 ? 'unknown (use count endpoint)' : 0;
    // Full count
    const all = await env.PUSH_SUBS.list();
    subCount = all.keys.length;
  } catch (e) {
    subCount = `error: ${e.message}`;
  }

  return new Response(JSON.stringify({
    status: 'ok',
    vapid_public_set: hasVapidPub,
    vapid_private_set: hasVapidPriv,
    api_token_set: hasApiToken,
    vapid_pub_prefix: hasVapidPub ? env.VAPID_PUBLIC_KEY.slice(0, 20) + '…' : null,
    subscription_count: subCount,
  }), {
    status: 200,
    headers: { ...cors, 'Content-Type': 'application/json' },
  });
}

// ─── Debug: clear all subscriptions ──────────────────────────────────────────

async function handleClearAll(request, env, cors) {
  let body;
  try { body = await request.json(); } catch { return forbidden(cors); }
  if (!tokenOk(body.token, env.API_TOKEN)) return forbidden(cors);

  let deleted = 0;
  let cursor;
  let done = false;
  do {
    const listResult = await env.PUSH_SUBS.list({ cursor, limit: 50 });
    done = listResult.list_complete;
    cursor = listResult.cursor;
    const batch = listResult.keys;
    if (batch.length > 0) {
      await Promise.all(batch.map(k => env.PUSH_SUBS.delete(k.name)));
      deleted += batch.length;
    }
  } while (!done);

  return new Response(JSON.stringify({ status: 'ok', deleted }), {
    status: 200,
    headers: { ...cors, 'Content-Type': 'application/json' },
  });
}

// ─── Concurrency Limiter ────────────────────────────────────────────────────

async function limitedConcurrency(items, concurrency, fn) {
  const results = [];
  const queue = [...items];

  async function worker() {
    while (queue.length > 0) {
      const item = queue.shift();
      results.push(await fn(item));
    }
  }

  const workers = Array.from({ length: Math.min(concurrency, items.length) }, () => worker());
  await Promise.all(workers);
  return results;
}

// ─── VAPID JWT Generation ──────────────────────────────────────────────────

async function generateVapidHeaders(endpoint, subject, privateKeyBase64, publicKeyBase64) {
  const url = new URL(endpoint);
  const origin = `${url.protocol}//${url.host}`;
  const now = Math.floor(Date.now() / 1000);

  // Normalize keys: accept both standard base64 and base64url
  const normalizeKey = (k) => k.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');

  const jwtHeader = base64UrlEncode(encoder.encode(JSON.stringify({ typ: 'JWT', alg: 'ES256' })));
  const jwtPayload = base64UrlEncode(encoder.encode(JSON.stringify({ aud: origin, exp: now + 43200, sub: subject })));
  const signingInput = `${jwtHeader}.${jwtPayload}`;

  let privateKeyBytes = base64UrlDecode(normalizeKey(privateKeyBase64));
  let privateKey;

  // If private key is 32 bytes raw (PKCS8 would be ~138 bytes), wrap in PKCS8 DER
  if (privateKeyBytes.length === 32) {
    // Wrap raw EC private key in PKCS#8 DER for Web Crypto import
    // The public key is embedded in the DER as an optional field
    const pubKeyBytes = base64UrlDecode(normalizeKey(publicKeyBase64));
    privateKeyBytes = buildPkcs8PrivateKey(privateKeyBytes, pubKeyBytes);
  }

  privateKey = await crypto.subtle.importKey(
    'pkcs8',
    privateKeyBytes,
    { name: 'ECDSA', namedCurve: 'P-256' },
    false,
    ['sign'],
  );

  const signature = await crypto.subtle.sign(
    { name: 'ECDSA', hash: { name: 'SHA-256' } },
    privateKey,
    encoder.encode(signingInput),
  );

  const token = `${signingInput}.${base64UrlEncode(new Uint8Array(signature))}`;
  const publicKeyBase64Url = base64UrlEncode(base64UrlDecode(normalizeKey(publicKeyBase64)));

  // RFC 8292 (VAPID): Use the compact serialization format
  // Authorization: vapid t=<jwt>, k=<public_key_base64url>
  // This is the format expected by FCM and modern push services
  return {
    Authorization: `vapid t=${token}, k=${publicKeyBase64Url}`,
  };
}

// ─── Web Push Encryption (RFC 8291 - aes128gcm) ────────────────────────────

async function webPushEncrypt(payload, clientPublicKeyBase64, authBase64) {
  const plaintext = encoder.encode(payload);
  const uaPublic = base64UrlDecode(clientPublicKeyBase64);
  const authSecret = base64UrlDecode(authBase64);

  // Generate ephemeral ECDH key pair
  const serverKey = await crypto.subtle.generateKey(
    { name: 'ECDH', namedCurve: 'P-256' },
    true,
    ['deriveBits'],
  );

  const asPublic = new Uint8Array(await crypto.subtle.exportKey('raw', serverKey.publicKey));
  const uaKey = await crypto.subtle.importKey(
    'raw',
    uaPublic,
    { name: 'ECDH', namedCurve: 'P-256' },
    true,
    [],
  );

  // ECDH shared secret
  const ecdhSecret = new Uint8Array(
    await crypto.subtle.deriveBits({ name: 'ECDH', public: uaKey }, serverKey.privateKey, 256),
  );

  const salt = crypto.getRandomValues(new Uint8Array(16));
  const keyInfo = concatBytes(encoder.encode('WebPush: info\0'), uaPublic, asPublic);
  const ikm = await hkdf(authSecret, ecdhSecret, keyInfo, 32);
  const cek = await hkdf(salt, ikm, encoder.encode('Content-Encoding: aes128gcm\0'), 16);
  const nonce = await hkdf(salt, ikm, encoder.encode('Content-Encoding: nonce\0'), 12);
  const record = concatBytes(plaintext, new Uint8Array([0x02]));

  const aesKey = await crypto.subtle.importKey('raw', cek, { name: 'AES-GCM' }, false, ['encrypt']);

  const ciphertext = new Uint8Array(await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv: nonce, tagLength: 128 },
    aesKey,
    record,
  ));

  const recordSize = Math.max(4096, ciphertext.length + 1);
  const header = new Uint8Array(16 + 4 + 1 + asPublic.length);
  header.set(salt, 0);
  new DataView(header.buffer).setUint32(16, recordSize, false);
  header[20] = asPublic.length;
  header.set(asPublic, 21);
  return concatBytes(header, ciphertext);
}

// HKDF extract + expand, RFC 5869.
async function hkdf(salt, ikm, info, length) {
  const extractKey = await crypto.subtle.importKey(
    'raw', salt, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'],
  );
  const prk = new Uint8Array(await crypto.subtle.sign('HMAC', extractKey, ikm));
  const expandKey = await crypto.subtle.importKey(
    'raw', prk, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'],
  );
  let output = new Uint8Array(0);
  let previous = new Uint8Array(0);
  for (let i = 1; output.length < length; i++) {
    previous = new Uint8Array(await crypto.subtle.sign(
      'HMAC', expandKey, concatBytes(previous, info, new Uint8Array([i])),
    ));
    output = concatBytes(output, previous);
  }
  return output.slice(0, length);
}

// ─── PKCS#8 DER builder for P-256 EC private key ──────────────────────────

function buildPkcs8PrivateKey(rawPrivKey, rawPubKey) {
  // Build ECPrivateKey SEQUENCE per SEC 1
  // ECPrivateKey ::= SEQUENCE {
  //   version        INTEGER { ecPrivkeyVer1(1) } (1 byte: 02 01 01)
  //   privateKey     OCTET STRING
  //   parameters [0] ECParameters {{ NamedCurve }} OPTIONAL
  //   publicKey  [1] BIT STRING OPTIONAL
  // }

  // Named curve OID for P-256 / secp256r1: 1.2.840.10045.3.1.7
  const curveOidBytes = new Uint8Array([0x06, 0x08, 0x2a, 0x86, 0x48, 0xce, 0x3d, 0x03, 0x01, 0x07]);

  // Private key OCTET STRING
  const privOctetStr = derOctetString(rawPrivKey);

  // Public key BIT STRING (tagged [1] EXPLICIT)
  // BIT STRING needs a leading 0x00 byte for unused bits (unused bits = 0)
  const pubBitStringContent = new Uint8Array([0x00, ...rawPubKey]);
  const pubBitString = derBitString(pubBitStringContent);
  const pubTagged = derTagged(1, pubBitString);

  // parameters [0] = curve OID
  const paramsTagged = derTagged(0, curveOidBytes);

  // ECPrivateKey SEQUENCE content
  const ecSeqBody = concatBytes(
    derInteger(1),     // version = 1
    privOctetStr,      // privateKey
    paramsTagged,     // parameters [0]
    pubTagged,        // publicKey [1]
  );
  const ecSeq = derSequence(ecSeqBody);

  // PKCS#8 wrapper
  // PrivateKeyInfo ::= SEQUENCE {
  //   version                   INTEGER (0)
  //   privateKeyAlgorithm       AlgorithmIdentifier
  //   privateKey                OCTET STRING (containing ECPrivateKey)
  // }

  // AlgorithmIdentifier for id-ecPublicKey + P-256
  const algoId = derSequence(new Uint8Array([
    0x06, 0x07, 0x2a, 0x86, 0x48, 0xce, 0x3d, 0x02, 0x01,  // id-ecPublicKey
    0x06, 0x08, 0x2a, 0x86, 0x48, 0xce, 0x3d, 0x03, 0x01, 0x07,  // secp256r1
  ]));

  const pkcs8Body = concatBytes(
    derInteger(0),    // version = 0
    algoId,           // algorithm
    derOctetString(ecSeq),  // privateKey (wrapped ECPrivateKey)
  );

  return derSequence(pkcs8Body);
}

// DER helper functions

function derSequence(content) {
  const tag = 0x30; // SEQUENCE (constructed)
  return concatBytes(new Uint8Array([tag]), derLength(content.length), content);
}

function derInteger(value) {
  if (value < 128) return new Uint8Array([0x02, 0x01, value]);
  // Only handles values < 256 for simplicity
  return new Uint8Array([0x02, 0x01, value & 0xff]);
}

function derOctetString(bytes) {
  const len = bytes.length;
  if (len < 128) {
    return concatBytes(new Uint8Array([0x04, len]), bytes);
  }
  // Long form (len >= 128)
  const lenBytes = [];
  let tmp = len;
  while (tmp > 0) { lenBytes.unshift(tmp & 0xff); tmp >>= 8; }
  return concatBytes(new Uint8Array([0x04, 0x80 | lenBytes.length, ...lenBytes]), bytes);
}

function derBitString(bytes) {
  const len = bytes.length;
  if (len < 128) {
    return concatBytes(new Uint8Array([0x03, len]), bytes);
  }
  // Long form
  const lenBytes = [];
  let tmp = len;
  while (tmp > 0) { lenBytes.unshift(tmp & 0xff); tmp >>= 8; }
  return concatBytes(new Uint8Array([0x03, 0x80 | lenBytes.length, ...lenBytes]), bytes);
}

function derTagged(tag, content) {
  return concatBytes(new Uint8Array([0xa0 | tag]), derLength(content.length), content);
}

function derLength(len) {
  if (len < 128) return new Uint8Array([len]);
  const bytes = [];
  let tmp = len;
  while (tmp > 0) { bytes.unshift(tmp & 0xff); tmp >>= 8; }
  return new Uint8Array([0x80 | bytes.length, ...bytes]);
}

function concatBytes(...arrays) {
  const totalLen = arrays.reduce((acc, a) => acc + a.length, 0);
  const result = new Uint8Array(totalLen);
  let offset = 0;
  for (const a of arrays) {
    result.set(a, offset);
    offset += a.length;
  }
  return result;
}

// ─── Base64 URL helpers ─────────────────────────────────────────────────────

function base64UrlDecode(str) {
  const base64 = str.replace(/-/g, '+').replace(/_/g, '/');
  const padding = base64.length % 4 === 0 ? 0 : 4 - (base64.length % 4);
  const binary = atob(base64 + '===='.slice(0, padding));
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function base64UrlEncode(bytes) {
  let binary = '';
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');
}

export { webPushEncrypt, generateVapidHeaders, buildNotificationPayload };
