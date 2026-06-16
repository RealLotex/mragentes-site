// MR Agentes — Cloudflare Worker for Web Push
// Deploy: wrangler deploy cloudflare-worker.js --name mragentes-push
// Routes: your-worker.your-subdomain.workers.dev

// === CONFIG ===
const VAPID_PUBLIC_KEY = 'BCanmq68wMsvVuDW-DVQO349Uj1HvP7D6qdHc9oC8L89CQ8JEddWf6On1pWjkMYuHqMK_jckdp6U88C6h9s4Vbk';
const VAPID_PRIVATE_KEY = '6KmIThJ5kQDWWaZYMeft_cGifvMTLyfvvzNhnI1d-eQ';
const API_TOKEN = '***'; // same as before

// === KV NAMESPACE (bind as PUSH_SUBS) ===
// wrangler.toml:
// [[kv_namespaces]]
// binding = "PUSH_SUBS"
// id = "your-kv-id"

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    // CORS headers for all responses
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    try {
      if (path === '/api/subscribe/' && request.method === 'POST') {
        return await handleSubscribe(request, env, corsHeaders);
      }
      if (path === '/api/unsubscribe/' && request.method === 'POST') {
        return await handleUnsubscribe(request, env, corsHeaders);
      }
      if (path === '/api/send/' && request.method === 'POST') {
        return await handleSend(request, env, corsHeaders);
      }
      if (path === '/api/vapid-key/' && request.method === 'GET') {
        return new Response(JSON.stringify({ publicKey: VAPID_PUBLIC_KEY }), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' },
        });
      }

      return new Response('Not found', { status: 404, headers: corsHeaders });
    } catch (e) {
      return new Response(JSON.stringify({ error: e.message }), {
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }
  },
};

async function handleSubscribe(request, env, cors) {
  const body = await request.json();
  const endpoint = body.endpoint;
  if (!endpoint) {
    return new Response(JSON.stringify({ error: 'Missing endpoint' }), {
      status: 400, headers: { ...cors, 'Content-Type': 'application/json' },
    });
  }

  // Check if exists
  const existing = await env.PUSH_SUBS.get(endpoint);
  if (!existing) {
    await env.PUSH_SUBS.put(endpoint, JSON.stringify(body), {
      expirationTtl: 86400 * 365, // 1 year
    });
  }

  // Keep a list of all endpoints for batch sending
  const list = await env.PUSH_SUBS.get('__list__', { type: 'json' }).catch(() => null);
  const endpoints = list || [];
  if (!endpoints.includes(endpoint)) {
    endpoints.push(endpoint);
    await env.PUSH_SUBS.put('__list__', JSON.stringify(endpoints));
  }

  console.log(`[Push] Subscribed: ${endpoint.slice(0, 40)}...`);
  return new Response(JSON.stringify({ status: 'ok' }), {
    status: 200, headers: { ...cors, 'Content-Type': 'application/json' },
  });
}

async function handleUnsubscribe(request, env, cors) {
  const body = await request.json();
  const endpoint = body.endpoint;
  if (!endpoint) {
    return new Response(JSON.stringify({ error: 'Missing endpoint' }), {
      status: 400, headers: { ...cors, 'Content-Type': 'application/json' },
    });
  }

  await env.PUSH_SUBS.delete(endpoint);

  const list = await env.PUSH_SUBS.get('__list__', { type: 'json' }).catch(() => null);
  if (list) {
    const filtered = list.filter(e => e !== endpoint);
    await env.PUSH_SUBS.put('__list__', JSON.stringify(filtered));
  }

  console.log(`[Push] Unsubscribed: ${endpoint.slice(0, 40)}...`);
  return new Response(JSON.stringify({ status: 'ok' }), {
    status: 200, headers: { ...cors, 'Content-Type': 'application/json' },
  });
}

async function handleSend(request, env, cors) {
  const body = await request.json();

  // Auth
  if (body.token !== API_TOKEN) {
    return new Response(JSON.stringify({ error: 'Invalid token' }), {
      status: 403, headers: { ...cors, 'Content-Type': 'application/json' },
    });
  }

  const title = body.title || 'MR Agentes';
  const message = body.body || '';
  const url = body.url || 'https://mragentes.com.ar/';

  const list = await env.PUSH_SUBS.get('__list__', { type: 'json' }).catch(() => null);
  if (!list || list.length === 0) {
    return new Response(JSON.stringify({ status: 'ok', sent: 0 }), {
      status: 200, headers: { ...cors, 'Content-Type': 'application/json' },
    });
  }

  let sent = 0;
  let failed = 0;

  const payload = JSON.stringify({
    title,
    body: message,
    url,
    icon: '/images/favicon.png',
    badge: '/images/favicon.png',
    tag: `nota-${Date.now()}`,
    renotify: true,
  });

  const encoder = new TextEncoder();
  const payloadBytes = encoder.encode(payload);
  const payloadBase64 = btoa(String.fromCharCode(...new Uint8Array(payloadBytes)))
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_');

  for (const endpoint of list) {
    try {
      const subData = await env.PUSH_SUBS.get(endpoint, { type: 'json' });
      if (!subData || !subData.keys) continue;

      const res = await sendWebPush(endpoint, subData.keys, payloadBase64);
      if (res.ok) {
        sent++;
      } else {
        // If 410 Gone or 404, remove subscription
        if (res.status === 410 || res.status === 404) {
          await env.PUSH_SUBS.delete(endpoint);
          const newList = list.filter(e => e !== endpoint);
          await env.PUSH_SUBS.put('__list__', JSON.stringify(newList));
        }
        failed++;
      }
    } catch (e) {
      failed++;
    }
  }

  console.log(`[Push] Sent: ${sent}, Failed: ${failed}, Total: ${list.length}`);
  return new Response(JSON.stringify({ status: 'ok', sent, failed }), {
    status: 200, headers: { ...cors, 'Content-Type': 'application/json' },
  });
}

async function sendWebPush(endpoint, keys, payloadBase64) {
  const p256dh = keys.p256dh;
  const auth = keys.auth;

  // Generate VAPID headers
  const vapidHeaders = await generateVapidHeaders(
    endpoint,
    VAPID_PUBLIC_KEY,
    VAPID_PRIVATE_KEY,
    'mailto:marcos@mragentes.com.ar',
  );

  // Encrypt payload (simplified — web-push-encrypted)
  const encrypted = await encryptPayload(payloadBase64, p256dh, auth);

  return fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/octet-stream',
      'Content-Encoding': 'aes128gcm',
      'TTL': '86400',
      'Urgency': 'high',
      ...vapidHeaders,
    },
    body: encrypted,
  });
}

// === VAPID + ENCRYPTION ===
// (Using Web Crypto API available in Workers runtime)

async function generateVapidHeaders(endpoint, publicKey, privateKey, subject) {
  const url = new URL(endpoint);
  const origin = `${url.protocol}//${url.host}`;

  const header = {
    typ: 'JWT',
    alg: 'ES256',
  };

  const now = Math.floor(Date.now() / 1000);
  const payload = {
    aud: origin,
    exp: now + 43200, // 12 hours
    sub: subject,
  };

  const headerB64 = base64UrlEncode(encoder.encode(JSON.stringify(header)));
  const payloadB64 = base64UrlEncode(encoder.encode(JSON.stringify(payload)));
  const signingInput = `${headerB64}.${payloadB64}`;

  // Import private key
  const privateKeyBytes = base64UrlDecode(privateKey);
  const cryptoKey = await crypto.subtle.importKey(
    'pkcs8',
    privateKeyBytes,
    { name: 'ECDSA', namedCurve: 'P-256' },
    false,
    ['sign'],
  );

  const signature = await crypto.subtle.sign(
    { name: 'ECDSA', hash: { name: 'SHA-256' } },
    cryptoKey,
    encoder.encode(signingInput),
  );

  const sigB64 = base64UrlEncode(new Uint8Array(signature));
  const token = `${signingInput}.${sigB64}`;

  // Import public key for cryptoKey
  const publicKeyBytes = base64UrlDecode(publicKey);
  const publicKeyB64 = base64UrlEncode(publicKeyBytes);

  return {
    Authorization: `WebPush ${publicKeyB64}:${token}`,
  };
}

async function encryptPayload(payloadBase64, p256dh, auth) {
  // Simplified: return the payload as-is for workers that support it
  // Real encryption requires ECDH + AES-GCM. For now return raw.
  return encoder.encode(payloadBase64);
}

const encoder = new TextEncoder();

function base64UrlDecode(str) {
  const base64 = str.replace(/-/g, '+').replace(/_/g, '/');
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function base64UrlEncode(bytes) {
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');
}
