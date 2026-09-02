// MR Agentes — Cloudflare Worker for Web Push notifications.
//
// Runtime bindings:
//   PUSH_SUBS, API_TOKEN, VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY,
//   ALLOWED_ORIGINS. Optional adapters used by tests/local development:
//   FETCH, PUSH_TRANSPORT and CLOCK.

const encoder = new TextEncoder();
const decoder = new TextDecoder("utf-8", { fatal: true });

const SITE_ORIGIN = "https://mragentes.com.ar";
const BRAND_ICON = "/faviconhand512.png";
const BRAND_BADGE = "/faviconhand512.png";
const SCHEMA_VERSION = 1;
const SUBSCRIPTION_TTL_SECONDS = 31_536_000;
const MAX_REQUEST_BYTES = 16_384;
const DEFAULT_PAGE_SIZE = 50;
const DEFAULT_MAX_SUBSCRIPTIONS = 10_000;
const MAX_PUSH_PLAINTEXT_BYTES = 3_993;
const MAX_EVENT_ID_BYTES = 512;
const BLOG_NOTE_EVENT_RE = /^blog-note:\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01]):[\p{L}\p{N}]+(?:-[\p{L}\p{N}]+)*$/u;
const GITHUB_OIDC_ISSUER = "https://token.actions.githubusercontent.com";
const GITHUB_OIDC_JWKS_URL = `${GITHUB_OIDC_ISSUER}/.well-known/jwks`;
const GITHUB_OIDC_AUDIENCE = "mragentes-push-notify";
const GITHUB_OIDC_REPOSITORY = "RealLotex/mragentes-site";
const GITHUB_OIDC_REPOSITORY_ID = "1270433781";
const GITHUB_OIDC_REF = "refs/heads/main";
const GITHUB_OIDC_ENVIRONMENT = "cloudflare-production";
const GITHUB_OIDC_WORKFLOW_REF = `${GITHUB_OIDC_REPOSITORY}/.github/workflows/notify-note.yml@refs/heads/main`;
const GITHUB_OIDC_MAX_TOKEN_BYTES = 16_384;
const GITHUB_OIDC_MAX_TOKEN_AGE_SECONDS = 600;
const GITHUB_OIDC_CLOCK_SKEW_SECONDS = 30;
let githubOidcJwksCache = { expiresAt: 0, keys: [] };

class HttpError extends Error {
  constructor(status, message, publicCode = "bad_request") {
    super(message);
    this.name = "HttpError";
    this.status = status;
    this.publicCode = publicCode;
  }
}

function nowFrom(env) {
  const value = typeof env?.CLOCK === "function" ? env.CLOCK() : Date.now();
  return Number.isFinite(value) ? value : Date.now();
}

function isPlainObject(value) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function assertPlainObject(value, label) {
  if (!isPlainObject(value)) throw new HttpError(400, `${label} schema must be an object`);
}

function assertAllowedKeys(value, allowed, label) {
  const allowedSet = new Set(allowed);
  for (const key of Object.keys(value)) {
    if (!allowedSet.has(key)) throw new HttpError(400, `${label} schema has extra field ${key}`);
  }
}

function safeString(value, label) {
  if (typeof value !== "string") throw new HttpError(400, `${label} must be a string`);
  return value;
}

function jsonResponse(value, { status = 200, headers = {} } = {}) {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...headers },
  });
}

function requestIdFor(request) {
  const supplied = request.headers.get("X-Request-Id");
  if (supplied && /^[A-Za-z0-9._:-]{1,128}$/.test(supplied)) return supplied;
  return "request-unavailable";
}

function allowedOrigins(env) {
  const configured = Array.isArray(env?.ALLOWED_ORIGINS)
    ? env.ALLOWED_ORIGINS
    : String(env?.ALLOWED_ORIGINS || SITE_ORIGIN).split(",");
  return configured.map((value) => String(value).trim()).filter(Boolean);
}

function validateOrigin(origin, allowlist) {
  if (typeof origin !== "string" || !origin) return false;
  let parsed;
  try { parsed = new URL(origin); } catch { return false; }
  if (parsed.protocol !== "https:" || parsed.origin !== origin || parsed.username || parsed.password) return false;
  return Array.isArray(allowlist) && allowlist.some((candidate) => candidate === origin);
}

function corsHeaders(origin) {
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type, Idempotency-Key, X-Request-Id",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  };
}

function tokenOk(provided, expected) {
  if (typeof provided !== "string" || typeof expected !== "string") return false;
  if (!provided || !expected || provided.length !== expected.length) return false;
  let difference = 0;
  for (let index = 0; index < expected.length; index += 1) {
    difference |= provided.charCodeAt(index) ^ expected.charCodeAt(index);
  }
  return difference === 0;
}

function forbidden(cors = {}) {
  const response = jsonResponse({ error: "forbidden" }, { status: 403, headers: cors });
  // Keep the helper inspectable without consuming the returned response. The
  // actual routed response remains an ordinary Response object.
  response.json = () => response.clone().json();
  return response;
}

function unauthorized(headers = {}) {
  return jsonResponse({ error: "unauthorized" }, { status: 401, headers });
}

function bearerToken(request) {
  const value = request.headers.get("Authorization");
  if (typeof value !== "string") return null;
  const match = /^Bearer ([^\s]+)$/.exec(value);
  return match ? match[1] : null;
}

function jsonFromBase64Url(value) {
  try {
    const parsed = JSON.parse(decoder.decode(base64UrlDecode(value)));
    return isPlainObject(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function oidcAudienceOk(value) {
  if (typeof value === "string") return value === GITHUB_OIDC_AUDIENCE;
  return Array.isArray(value) && value.some((entry) => entry === GITHUB_OIDC_AUDIENCE);
}

function oidcInteger(value) {
  return typeof value === "number" && Number.isSafeInteger(value) ? value : null;
}

async function githubOidcKeys() {
  const now = Date.now();
  if (githubOidcJwksCache.expiresAt > now && githubOidcJwksCache.keys.length) {
    return githubOidcJwksCache.keys;
  }
  try {
    const response = await fetch(GITHUB_OIDC_JWKS_URL, { headers: { Accept: "application/json" } });
    if (!response.ok) return [];
    const body = await response.json();
    if (!isPlainObject(body) || !Array.isArray(body.keys)) return [];
    const keys = body.keys.filter((key) => (
      isPlainObject(key)
      && key.kty === "RSA"
      && key.alg === "RS256"
      && typeof key.kid === "string"
      && key.kid.length > 0
    ));
    if (!keys.length) return [];
    githubOidcJwksCache = { expiresAt: now + 300_000, keys };
    return keys;
  } catch {
    return [];
  }
}

async function githubActionsTokenOk(token, env) {
  if (typeof token !== "string" || !token || encoder.encode(token).byteLength > GITHUB_OIDC_MAX_TOKEN_BYTES) return false;
  const parts = token.split(".");
  if (parts.length !== 3 || parts.some((part) => !part)) return false;
  const [encodedHeader, encodedClaims, encodedSignature] = parts;
  const header = jsonFromBase64Url(encodedHeader);
  const claims = jsonFromBase64Url(encodedClaims);
  if (!header || !claims || header.alg !== "RS256" || typeof header.kid !== "string" || !/^[A-Za-z0-9._-]{1,256}$/.test(header.kid)) return false;
  const now = Math.floor(nowFrom(env) / 1_000);
  const exp = oidcInteger(claims.exp);
  const iat = oidcInteger(claims.iat);
  const nbf = oidcInteger(claims.nbf);
  if (
    claims.iss !== GITHUB_OIDC_ISSUER
    || !oidcAudienceOk(claims.aud)
    // GitHub can change the serialized subject format when immutable claims
    // are enabled. The signed repository, repository_id, ref, environment
    // and workflow_ref claims below are independently pinned instead.
    || claims.repository !== GITHUB_OIDC_REPOSITORY
    || String(claims.repository_id) !== GITHUB_OIDC_REPOSITORY_ID
    || claims.ref !== GITHUB_OIDC_REF
    || claims.environment !== GITHUB_OIDC_ENVIRONMENT
    || claims.workflow_ref !== GITHUB_OIDC_WORKFLOW_REF
    || exp === null || iat === null || nbf === null
    || exp <= now - GITHUB_OIDC_CLOCK_SKEW_SECONDS
    || nbf > now + GITHUB_OIDC_CLOCK_SKEW_SECONDS
    || iat > now + GITHUB_OIDC_CLOCK_SKEW_SECONDS
    || now - iat > GITHUB_OIDC_MAX_TOKEN_AGE_SECONDS
  ) return false;
  const key = (await githubOidcKeys()).find((candidate) => candidate.kid === header.kid);
  if (!key) return false;
  try {
    const cryptoRuntime = await runtimeCrypto();
    const imported = await cryptoRuntime.subtle.importKey(
      "jwk",
      key,
      { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
      false,
      ["verify"],
    );
    return await cryptoRuntime.subtle.verify(
      "RSASSA-PKCS1-v1_5",
      imported,
      base64UrlDecode(encodedSignature),
      encoder.encode(`${encodedHeader}.${encodedClaims}`),
    );
  } catch {
    return false;
  }
}

async function sendAuthorized(request, env) {
  const token = bearerToken(request);
  return tokenOk(token, env?.API_TOKEN) || githubActionsTokenOk(token, env);
}

function truncateUtf8(value, { maxCodePoints, maxBytes }) {
  const points = Array.from(value).slice(0, maxCodePoints);
  let output = "";
  let used = 0;
  for (const point of points) {
    const size = encoder.encode(point).length;
    if (used + size > maxBytes) break;
    output += point;
    used += size;
  }
  return output;
}

function canonicalNoteUrl(value) {
  if (typeof value !== "string") throw new HttpError(400, "url must be a string");
  const trimmed = value.trim();
  if (!trimmed) return `${SITE_ORIGIN}/`;
  let parsed;
  try { parsed = new URL(trimmed); } catch { throw new HttpError(400, "url is invalid"); }
  if (
    parsed.origin !== SITE_ORIGIN
    || parsed.protocol !== "https:"
    || parsed.username
    || parsed.password
    || parsed.port
    || parsed.search
    || parsed.hash
    || !/^\/notas\/[^/]+\/$/u.test(parsed.pathname)
  ) throw new HttpError(400, "url must be a canonical note URL on the site origin");
  return parsed.href;
}

function publicPostImage(value) {
  if (typeof value !== "string" || !value.trim()) return null;
  const raw = value.trim();
  if (raw.includes("\\") || raw.includes("?") || raw.includes("#")) return null;
  let decoded = raw;
  try {
    for (let round = 0; round < 3; round += 1) {
      const next = decodeURIComponent(decoded);
      if (next === decoded) break;
      decoded = next;
    }
  } catch { return null; }
  if (decoded.includes("\\") || /(?:^|\/)\.\.(?:\/|$)/.test(decoded)) return null;
  let image;
  try { image = new URL(raw, SITE_ORIGIN); } catch { return null; }
  if (
    image.origin !== SITE_ORIGIN
    || image.protocol !== "https:"
    || image.username
    || image.password
    || image.port
    || image.search
    || image.hash
    || !image.pathname.startsWith("/images/stock/")
    || !/\.(?:avif|jpe?g|png|webp)$/i.test(image.pathname)
  ) return null;
  let decodedPath;
  try { decodedPath = decodeURIComponent(image.pathname); } catch { return null; }
  if (decodedPath.includes("\\") || /(?:^|\/)\.\.(?:\/|$)/.test(decodedPath)) return null;
  return `${SITE_ORIGIN}${image.pathname}`;
}

function buildNotificationPayload(input = {}) {
  assertPlainObject(input, "notification payload");
  assertAllowedKeys(input, ["title", "body", "url", "image", "tag", "eventId", "icon", "badge"], "notification payload");
  for (const field of ["title", "body", "url", "image", "tag", "eventId", "icon", "badge"]) {
    if (input[field] !== undefined && typeof input[field] !== "string") {
      throw new HttpError(400, `${field} type is invalid`);
    }
  }
  const eventId = String(input.eventId || input.tag || "").trim();
  if (!eventId) throw new HttpError(400, "eventId is required");
  const titleSource = input.title?.trim() || "MR Agentes";
  const bodySource = input.body?.trim() || "Hay contenido nuevo disponible.";
  const url = input.url === undefined || !input.url.trim() ? `${SITE_ORIGIN}/` : canonicalNoteUrl(input.url);
  const image = publicPostImage(input.image);
  const payload = {
    title: truncateUtf8(titleSource, { maxCodePoints: 120, maxBytes: 240 }),
    body: truncateUtf8(bodySource, { maxCodePoints: 255, maxBytes: 510 }),
    url,
    icon: BRAND_ICON,
    badge: BRAND_BADGE,
    tag: truncateUtf8(eventId, { maxCodePoints: 120, maxBytes: 240 }),
    eventId,
  };
  if (image) payload.image = image;
  return payload;
}

function buildWelcomePayload({ eventId } = {}) {
  if (typeof eventId !== "string" || !eventId.trim()) throw new HttpError(400, "welcome eventId is required");
  return {
    title: "🔔 Bienvenido a MR Agentes",
    body: "Activaste las notificaciones. Ahora vas a recibir alertas cuando publiquemos una nota nueva.",
    url: `${SITE_ORIGIN}/`,
    icon: BRAND_ICON,
    badge: BRAND_BADGE,
    tag: eventId,
    eventId,
  };
}

function concatBytes(...arrays) {
  for (const value of arrays) {
    if (!(value instanceof Uint8Array)) throw new TypeError("concatBytes accepts Uint8Array values");
  }
  const total = arrays.reduce((sum, value) => sum + value.byteLength, 0);
  const result = new Uint8Array(total);
  let offset = 0;
  for (const value of arrays) {
    result.set(value, offset);
    offset += value.byteLength;
  }
  return result;
}

async function parseRequestBody(request, { maxBytes = MAX_REQUEST_BYTES } = {}) {
  if (!Number.isInteger(maxBytes) || maxBytes <= 0) throw new TypeError("maxBytes must be a positive integer");
  const contentType = request.headers.get("Content-Type") || "";
  if (!/^application\/json(?:\s*;\s*charset=(?:utf-8|utf8))?\s*$/i.test(contentType)) {
    throw new HttpError(415, "content-type must be application/json", "unsupported_media_type");
  }
  const declared = request.headers.get("Content-Length");
  if (declared !== null) {
    const length = Number(declared);
    if (!Number.isInteger(length) || length < 0) throw new HttpError(400, "invalid content-length");
    if (length > maxBytes) throw new HttpError(413, "request body exceeds maximum", "payload_too_large");
  }
  if (!request.body) throw new HttpError(400, "request body is empty");
  const reader = request.body.getReader();
  const chunks = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = value instanceof Uint8Array ? value : new Uint8Array(value);
      total += chunk.byteLength;
      if (total > maxBytes) {
        await reader.cancel("payload too large");
        throw new HttpError(413, "request body exceeds maximum", "payload_too_large");
      }
      chunks.push(chunk);
    }
  } finally {
    try { reader.releaseLock(); } catch { /* cancelled */ }
  }
  if (total === 0) throw new HttpError(400, "request body is empty");
  let parsed;
  try { parsed = JSON.parse(decoder.decode(concatBytes(...chunks))); }
  catch { throw new HttpError(400, "request body is invalid JSON"); }
  if (!isPlainObject(parsed)) throw new HttpError(400, "JSON body schema must be an object");
  return parsed;
}

function base64UrlDecode(value) {
  if (typeof value !== "string") throw new TypeError("base64url value must be a string");
  if (!/^[A-Za-z0-9_-]*={0,2}$/.test(value)) throw new Error("invalid base64url alphabet or padding");
  const firstPadding = value.indexOf("=");
  const unpadded = firstPadding === -1 ? value : value.slice(0, firstPadding);
  const padding = firstPadding === -1 ? "" : value.slice(firstPadding);
  if (unpadded.length % 4 === 1) throw new Error("invalid base64url length");
  const expectedPadding = (4 - (unpadded.length % 4)) % 4;
  if (padding && (value.length % 4 !== 0 || padding.length !== expectedPadding)) {
    throw new Error("non-canonical base64url padding");
  }
  const standard = unpadded.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat(expectedPadding);
  let binary;
  try { binary = atob(standard); } catch { throw new Error("invalid base64url encoding"); }
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  if (base64UrlEncode(bytes) !== unpadded) throw new Error("non-canonical base64url encoding");
  return bytes;
}

function base64UrlEncode(value) {
  const bytes = value instanceof Uint8Array ? value : value instanceof ArrayBuffer ? new Uint8Array(value) : null;
  if (!bytes) throw new TypeError("base64url input must be bytes");
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
  }
  return btoa(binary).replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
}

async function runtimeCrypto(candidate) {
  if (candidate?.subtle && typeof candidate.getRandomValues === "function") return candidate;
  if (globalThis.crypto?.subtle && typeof globalThis.crypto.getRandomValues === "function") return globalThis.crypto;
  // Node is a local-test fallback. Workers use the standards-based global above.
  const module = await import("node:crypto");
  return module.webcrypto;
}

async function sha256Bytes(value, cryptoOverride) {
  const cryptoApi = await runtimeCrypto(cryptoOverride);
  return new Uint8Array(await cryptoApi.subtle.digest("SHA-256", value));
}

async function sha256Hex(value, cryptoOverride) {
  const digest = await sha256Bytes(typeof value === "string" ? encoder.encode(value) : value, cryptoOverride);
  return Array.from(digest, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function validateSubscription(input) {
  assertPlainObject(input, "subscription");
  assertAllowedKeys(input, ["endpoint", "expirationTime", "keys", "revalidate"], "subscription");
  const endpoint = safeString(input.endpoint, "endpoint");
  if (!endpoint || encoder.encode(endpoint).length > 2_048) throw new HttpError(400, "endpoint length is invalid");
  if (!/^https:\/\/[^/]/.test(endpoint)) throw new HttpError(400, "endpoint HTTPS URL authority is invalid");
  let parsed;
  try { parsed = new URL(endpoint); } catch { throw new HttpError(400, "endpoint URL is invalid"); }
  if (parsed.protocol !== "https:" || !parsed.hostname || parsed.username || parsed.password) {
    throw new HttpError(400, "endpoint must be an HTTPS URL without credentials");
  }
  if (input.expirationTime !== null && input.expirationTime !== undefined && !Number.isFinite(input.expirationTime)) {
    throw new HttpError(400, "expirationTime must be null or finite");
  }
  assertPlainObject(input.keys, "subscription keys");
  assertAllowedKeys(input.keys, ["p256dh", "auth"], "subscription keys");
  const p256dh = safeString(input.keys.p256dh, "p256dh");
  const auth = safeString(input.keys.auth, "auth");
  let publicKey;
  let authKey;
  try { publicKey = base64UrlDecode(p256dh); } catch { throw new HttpError(400, "p256dh base64url key is invalid"); }
  try { authKey = base64UrlDecode(auth); } catch { throw new HttpError(400, "auth base64url key is invalid"); }
  if (publicKey.length !== 65 || publicKey[0] !== 0x04) throw new HttpError(400, "p256dh key length must be 65 bytes");
  if (authKey.length !== 16) throw new HttpError(400, "auth key length must be 16 bytes");
  return {
    endpoint,
    expirationTime: input.expirationTime ?? null,
    keys: { p256dh, auth },
  };
}

async function subscriptionKey(endpoint) {
  if (typeof endpoint !== "string" || !endpoint) throw new TypeError("endpoint is required");
  return `sub:v${SCHEMA_VERSION}:${await sha256Hex(endpoint)}`;
}

function parseCanonicalSubscriptionRecord(raw) {
  const record = JSON.parse(raw);
  if (!isPlainObject(record) || record.schemaVersion !== SCHEMA_VERSION) {
    throw new Error("subscription record schema is invalid");
  }
  return {
    record,
    subscription: validateSubscription(record.subscription),
  };
}

function parseLegacySubscriptionRecord(raw, legacyKey) {
  const subscription = validateSubscription(JSON.parse(raw));
  if (subscription.endpoint !== legacyKey) {
    throw new Error("legacy subscription key does not match endpoint");
  }
  return subscription;
}

function validLegacySubscriptionRecord(raw, legacyKey) {
  if (raw === null) return null;
  try { return parseLegacySubscriptionRecord(raw, legacyKey); }
  catch { return null; }
}

function keyComponent(value) {
  return base64UrlEncode(encoder.encode(String(value)));
}

function keyNamespace(value) {
  const string = String(value);
  return /^[a-z0-9-]{1,40}$/i.test(string) ? string : keyComponent(string);
}

function notificationKey(namespace, identity) {
  return `notification:${keyNamespace(namespace)}:v${SCHEMA_VERSION}:${keyComponent(identity)}`;
}

function deliveryKey(eventId, subKey) {
  return `delivery:v${SCHEMA_VERSION}:${keyComponent(eventId)}:${keyComponent(subKey)}`;
}

function rateLimitKey(bucket, identity) {
  return `rate:v${SCHEMA_VERSION}:${keyComponent(bucket)}:${keyComponent(identity)}`;
}

async function enforceRateLimit(store, { bucket, identity, limit, windowSeconds, now = Date.now() }) {
  if (typeof bucket !== "string" || !bucket || typeof identity !== "string" || !identity) {
    throw new TypeError("rate limit bucket and identity are required");
  }
  if (!Number.isInteger(limit) || limit <= 0 || !Number.isInteger(windowSeconds) || windowSeconds <= 0) {
    throw new TypeError("rate limit and windowSeconds must be positive integers");
  }
  const key = rateLimitKey(bucket, identity);
  const raw = await store.get(key);
  let state;
  try { state = raw ? JSON.parse(raw) : null; } catch { state = null; }
  const windowMs = windowSeconds * 1_000;
  const fresh = state && Number.isFinite(state.startedAt) && now - state.startedAt < windowMs;
  const count = fresh ? Number(state.count) || 0 : 0;
  const startedAt = fresh ? state.startedAt : now;
  if (count >= limit) return { allowed: false, remaining: 0, resetAt: startedAt + windowMs };
  const next = { schemaVersion: SCHEMA_VERSION, bucket, count: count + 1, startedAt, updatedAt: now };
  await store.put(key, JSON.stringify(next), { expirationTtl: windowSeconds });
  return { allowed: true, remaining: Math.max(0, limit - next.count), resetAt: startedAt + windowMs };
}

// Local fallback for tests and single-isolate development. Production fan-out
// should bind the NotificationCoordinator Durable Object for global ordering.
const bindingLocks = new WeakMap();

async function withBindingLock(binding, identity, operation) {
  let locks = bindingLocks.get(binding);
  if (!locks) {
    locks = new Map();
    bindingLocks.set(binding, locks);
  }
  const previous = locks.get(identity) || Promise.resolve();
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  const tail = previous.catch(() => undefined).then(() => gate);
  locks.set(identity, tail);
  await previous.catch(() => undefined);
  try { return await operation(); }
  finally {
    release();
    if (locks.get(identity) === tail) locks.delete(identity);
  }
}

function classifyPushResponse(value) {
  if (!(value instanceof Response)) return "uncertain";
  if (value.status === 201 || value.status === 202) return "delivered";
  if (value.status === 404 || value.status === 410) return "gone";
  if ([408, 425, 429].includes(value.status) || value.status >= 500) return "retryable";
  return "invalid";
}

async function defaultPushTransport(subscription, payload, env) {
  if (!env?.VAPID_PRIVATE_KEY || !env?.VAPID_PUBLIC_KEY) throw new Error("push transport is not configured");
  const vapidHeaders = await generateVapidHeaders(
    subscription.endpoint,
    "mailto:admin@mragentes.com.ar",
    env.VAPID_PRIVATE_KEY,
    env.VAPID_PUBLIC_KEY,
  );
  const encrypted = await webPushEncrypt(JSON.stringify(payload), subscription.keys.p256dh, subscription.keys.auth);
  const transport = env.FETCH_PUSH || globalThis.fetch;
  if (typeof transport !== "function") throw new Error("push transport is unavailable");
  return transport(subscription.endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/octet-stream",
      "Content-Encoding": "aes128gcm",
      TTL: "86400",
      Urgency: "high",
      ...vapidHeaders,
    },
    body: encrypted,
  });
}

async function sendWelcomePush(subscription, env, subKey = "sub:v1:unknown") {
  const payload = buildWelcomePayload({ eventId: `welcome:${keyComponent(subKey)}` });
  const transport = typeof env?.PUSH_TRANSPORT === "function"
    ? env.PUSH_TRANSPORT
    : (sub, message) => defaultPushTransport(sub, message, env);
  try {
    let response = await transport(subscription, payload);
    let outcome = classifyPushResponse(response);
    if (outcome === "gone") await env.PUSH_SUBS.delete(subKey);
    if (outcome === "retryable") {
      response = await transport(subscription, payload);
      outcome = classifyPushResponse(response);
      if (outcome === "gone") await env.PUSH_SUBS.delete(subKey);
    }
    return outcome;
  } catch { return "uncertain"; }
}

async function handleSubscribe(request, env, cors, ctx) {
  const body = await parseRequestBody(request);
  const revalidated = body.revalidate === true;
  const subscription = validateSubscription(body);
  if (env.SUBSCRIBE_RATE_LIMIT !== undefined) {
    const identity = request.headers.get("CF-Connecting-IP") || "unknown";
    const result = await enforceRateLimit(env.PUSH_SUBS, {
      bucket: "subscribe",
      identity,
      limit: Number(env.SUBSCRIBE_RATE_LIMIT),
      windowSeconds: Number(env.SUBSCRIBE_RATE_WINDOW || 60),
      now: nowFrom(env),
    });
    if (!result.allowed) throw new HttpError(429, "subscribe rate limit exceeded", "rate_limited");
  }
  const key = await subscriptionKey(subscription.endpoint);
  const result = await withBindingLock(env.PUSH_SUBS, key, async () => {
    const existingRaw = await env.PUSH_SUBS.get(key);
    const legacyRaw = await env.PUSH_SUBS.get(subscription.endpoint);
    const legacySubscription = validLegacySubscriptionRecord(legacyRaw, subscription.endpoint);
    let existing = null;
    try { existing = existingRaw ? JSON.parse(existingRaw) : null; } catch { existing = null; }
    // A legacy URL-keyed record represents an existing browser registration.
    // Treat even an unparseable value at that exact reserved key as existing so
    // a repair never emits a second welcome notification. Only a validated
    // legacy record is removed after the canonical write succeeds.
    const created = existingRaw === null && legacyRaw === null;
    const timestamp = nowFrom(env);
    await env.PUSH_SUBS.put(key, JSON.stringify({
      schemaVersion: SCHEMA_VERSION,
      subscription,
      createdAt: Number.isFinite(existing?.createdAt) ? existing.createdAt : timestamp,
      updatedAt: timestamp,
    }), {
      expirationTtl: SUBSCRIPTION_TTL_SECONDS,
      metadata: { schemaVersion: SCHEMA_VERSION },
    });
    if (legacySubscription) await env.PUSH_SUBS.delete(subscription.endpoint);
    return { created };
  });
  const welcomeScheduled = result.created && !revalidated;
  if (welcomeScheduled) ctx.waitUntil(sendWelcomePush(subscription, env, key).catch(() => "uncertain"));
  return jsonResponse({ status: "ok", created: result.created, revalidated, welcomeScheduled }, {
    status: revalidated ? 200 : result.created ? 201 : 200,
    headers: cors,
  });
}

function validateUnsubscribeBody(body) {
  assertPlainObject(body, "unsubscribe");
  assertAllowedKeys(body, ["endpoint"], "unsubscribe");
  const endpoint = safeString(body.endpoint, "endpoint");
  if (!endpoint || encoder.encode(endpoint).length > 2_048) throw new HttpError(400, "endpoint length is invalid");
  if (!/^https:\/\/[^/]/.test(endpoint)) throw new HttpError(400, "endpoint HTTPS URL authority is invalid");
  let parsed;
  try { parsed = new URL(endpoint); } catch { throw new HttpError(400, "endpoint URL is invalid"); }
  if (parsed.protocol !== "https:" || !parsed.hostname || parsed.username || parsed.password) {
    throw new HttpError(400, "endpoint must be an HTTPS URL without credentials");
  }
  return endpoint;
}

async function handleUnsubscribe(request, env, cors) {
  const endpoint = validateUnsubscribeBody(await parseRequestBody(request));
  const key = await subscriptionKey(endpoint);
  const removed = await withBindingLock(env.PUSH_SUBS, key, async () => {
    const canonical = await env.PUSH_SUBS.get(key);
    const legacy = await env.PUSH_SUBS.get(endpoint);
    if (canonical === null && legacy === null) return false;
    if (canonical !== null) await env.PUSH_SUBS.delete(key);
    if (legacy !== null) await env.PUSH_SUBS.delete(endpoint);
    return true;
  });
  return jsonResponse({ status: "ok", removed }, { headers: cors });
}

function validateNotificationEvent(input) {
  assertPlainObject(input, "notification event");
  assertAllowedKeys(input, ["eventId", "payloadHash", "payload", "failpoint"], "notification event");
  const eventId = safeString(input.eventId, "eventId");
  if (
    eventId !== eventId.normalize("NFC")
    || encoder.encode(eventId).length > MAX_EVENT_ID_BYTES
    || !BLOG_NOTE_EVENT_RE.test(eventId)
  ) {
    throw new HttpError(400, "eventId must identify a new blog-note event");
  }
  const payloadHash = safeString(input.payloadHash, "payloadHash");
  if (!/^sha256:[a-f0-9]{64}$/.test(payloadHash)) throw new HttpError(400, "payloadHash must be sha256 hex");
  assertPlainObject(input.payload, "payload");
  assertAllowedKeys(input.payload, ["title", "body", "url", "image"], "payload");
  for (const field of ["title", "body", "url"]) {
    if (typeof input.payload[field] !== "string" || !input.payload[field].trim()) {
      throw new HttpError(400, `payload ${field} is required`);
    }
  }
  return {
    eventId,
    payloadHash,
    payload: buildNotificationPayload({ ...input.payload, eventId }),
    failpoint: input.failpoint,
  };
}

function summarizeDeliveries(outcomes) {
  const summary = { total: outcomes.length, delivered: 0, gone: 0, retryable: 0, uncertain: 0, invalid: 0 };
  for (const outcome of outcomes) {
    if (Object.prototype.hasOwnProperty.call(summary, outcome) && outcome !== "total") summary[outcome] += 1;
  }
  const state = summary.uncertain > 0 ? "uncertain" : summary.retryable > 0 ? "partial" : "complete";
  return { ...summary, state };
}

async function deleteSubscriptionRecords(kv, keys) {
  const uniqueKeys = [...new Set(keys.filter((key) => typeof key === "string" && key))];
  for (const key of uniqueKeys) await kv.delete(key);
}

async function applyDeliveryOutcome({ kv, subscriptionKey: key, subscriptionKeys, response }) {
  const outcome = classifyPushResponse(response);
  if (outcome === "gone") await deleteSubscriptionRecords(kv, subscriptionKeys || [key]);
  return outcome;
}

async function retryDelivery({ outcome, attempt, transport }) {
  if (outcome !== "retryable" || attempt >= 2) return { outcome, attempt };
  try {
    const response = await transport();
    return { outcome: classifyPushResponse(response), attempt: attempt + 1, response };
  } catch { return { outcome: "uncertain", attempt: attempt + 1 }; }
}

async function listSubscriptionsPaginated(kv, { pageSize = DEFAULT_PAGE_SIZE, maxTotal = DEFAULT_MAX_SUBSCRIPTIONS } = {}) {
  if (!Number.isInteger(pageSize) || pageSize <= 0) throw new TypeError("pageSize must be positive");
  if (!Number.isInteger(maxTotal) || maxTotal < 0) throw new TypeError("maxTotal must be non-negative");
  const byEndpoint = new Map();
  const invalid = new Set();

  function assertUniqueCapacity(endpoint) {
    if (!byEndpoint.has(endpoint) && byEndpoint.size >= maxTotal) {
      throw new HttpError(413, "subscription fan-out maximum exceeded", "too_many_subscriptions");
    }
  }

  async function scanPrefix(prefix, legacy) {
    const seenCursors = new Set();
    const seenKeys = new Set();
    let cursor;
    while (true) {
      const page = await kv.list({ prefix, cursor, limit: pageSize });
      for (const { name } of page.keys) {
        if (typeof name !== "string" || !name.startsWith(prefix) || seenKeys.has(name)) continue;
        seenKeys.add(name);
        const raw = await kv.get(name);
        if (legacy) {
          const subscription = validLegacySubscriptionRecord(raw, name);
          if (!subscription) continue;
          const existing = byEndpoint.get(subscription.endpoint);
          if (existing) {
            if (!existing.storageKeys.includes(name)) existing.storageKeys.push(name);
            continue;
          }
          assertUniqueCapacity(subscription.endpoint);
          byEndpoint.set(subscription.endpoint, {
            key: await subscriptionKey(subscription.endpoint),
            storageKeys: [name],
            subscription,
          });
          continue;
        }

        if (raw === null) {
          invalid.add(name);
          continue;
        }
        try {
          const { subscription } = parseCanonicalSubscriptionRecord(raw);
          const existing = byEndpoint.get(subscription.endpoint);
          if (existing) {
            if (!existing.storageKeys.includes(name)) existing.storageKeys.push(name);
            continue;
          }
          assertUniqueCapacity(subscription.endpoint);
          byEndpoint.set(subscription.endpoint, {
            key: name,
            storageKeys: [name],
            subscription,
          });
        } catch { invalid.add(name); }
      }
      if (page.list_complete) break;
      if (!page.cursor || seenCursors.has(page.cursor)) throw new Error("KV cursor cycle detected");
      seenCursors.add(page.cursor);
      cursor = page.cursor;
    }
  }

  // Canonical records are scanned first, so an endpoint present in both
  // layouts always uses the versioned hashed record. Prefix scans avoid
  // traversing unrelated rate-limit, delivery and notification state.
  await scanPrefix("sub:", false);
  await scanPrefix("https://", true);
  return { items: [...byEndpoint.values()], invalid: [...invalid] };
}

async function limitedConcurrency(items, concurrency, callback) {
  if (!Number.isInteger(concurrency) || concurrency <= 0) throw new TypeError("concurrency must be a positive integer");
  if (!Array.isArray(items) || typeof callback !== "function") throw new TypeError("items and callback are required");
  const results = new Array(items.length);
  let nextIndex = 0;
  async function worker() {
    while (nextIndex < items.length) {
      const index = nextIndex;
      nextIndex += 1;
      results[index] = await callback(items[index], index);
    }
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, items.length) }, () => worker()));
  return results;
}

function fanoutRecordKey(eventId) { return notificationKey("blog-note", eventId); }

function notificationCoordinatorStub(env, eventId) {
  const namespace = env.NOTIFICATION_COORDINATOR;
  if (!namespace) return null;
  if (typeof namespace.idFromName !== "function" || typeof namespace.get !== "function") {
    throw new Error("NotificationCoordinator binding is invalid");
  }
  return namespace.get(namespace.idFromName(eventId));
}

async function acquireFanout(env, event) {
  const coordinator = notificationCoordinatorStub(env, event.eventId);
  if (coordinator) {
    const result = await coordinator.acquireNotification({
      eventId: event.eventId,
      payloadHash: event.payloadHash,
    });
    const record = result.record || await coordinator.getNotification(event.eventId);
    return { ...result, record, coordinator, key: null };
  }
  const key = fanoutRecordKey(event.eventId);
  return withBindingLock(env.PUSH_SUBS, key, async () => {
    const raw = await env.PUSH_SUBS.get(key);
    if (raw) {
      let existing;
      try { existing = JSON.parse(raw); } catch { throw new HttpError(409, "notification state is corrupt", "conflict"); }
      if (existing.payloadHash !== event.payloadHash) throw new HttpError(409, "eventId payload conflict", "conflict");
      return { acquired: false, duplicate: true, record: existing, key };
    }
    const timestamp = nowFrom(env);
    const record = {
      schemaVersion: SCHEMA_VERSION,
      eventId: event.eventId,
      payloadHash: event.payloadHash,
      state: "pending",
      createdAt: timestamp,
      updatedAt: timestamp,
    };
    await env.PUSH_SUBS.put(key, JSON.stringify(record), { expirationTtl: 90 * 86_400 });
    return { acquired: true, duplicate: false, record, key };
  });
}

async function deploymentGate(url, env) {
  const transport = env.FETCH || globalThis.fetch;
  if (typeof transport !== "function") throw new HttpError(409, "deployment gate transport unavailable", "not_deployed");
  let response;
  try { response = await transport(url, { method: "HEAD", redirect: "manual" }); }
  catch { throw new HttpError(409, "note deployment could not be verified", "not_deployed"); }
  if (response.status !== 200) throw new HttpError(409, "note is not deployed", "not_deployed");
  if (response.url) {
    const actual = new URL(response.url);
    if (actual.origin !== SITE_ORIGIN || actual.href !== url) throw new HttpError(409, "deployment gate changed origin", "not_deployed");
  }
}

async function handleSend(request, env, cors) {
  if (!tokenOk(bearerToken(request), env.API_TOKEN)) return unauthorized(cors);
  const event = validateNotificationEvent(await parseRequestBody(request));
  if (request.headers.get("Idempotency-Key") !== event.eventId) {
    throw new HttpError(409, "Idempotency-Key conflicts with eventId", "conflict");
  }
  await deploymentGate(event.payload.url, env);
  const acquired = await acquireFanout(env, event);
  if (!acquired.acquired) {
    const previous = acquired.record.summary || summarizeDeliveries([]);
    return jsonResponse({ eventId: event.eventId, ...previous, duplicate: true }, { headers: cors });
  }
  const listed = await listSubscriptionsPaginated(env.PUSH_SUBS, {
    pageSize: Number(env.PUSH_PAGE_SIZE || DEFAULT_PAGE_SIZE),
    maxTotal: Number(env.MAX_SUBSCRIPTIONS || DEFAULT_MAX_SUBSCRIPTIONS),
  });
  for (const key of listed.invalid) await env.PUSH_SUBS.delete(key);
  const outcomes = listed.invalid.map(() => "invalid");
  const transport = typeof env.PUSH_TRANSPORT === "function"
    ? env.PUSH_TRANSPORT
    : (subscription, payload) => defaultPushTransport(subscription, payload, env);
  const delivered = await limitedConcurrency(listed.items, Number(env.PUSH_CONCURRENCY || 10), async ({ key, storageKeys, subscription }) => {
    const coordinator = acquired.coordinator;
    try {
      if (coordinator) {
        const delivery = await coordinator.acquireDelivery({
          eventId: event.eventId,
          subscriptionKey: key,
        });
        if (!delivery.acquired) return delivery.state === "pending" || delivery.state === "attempting"
          ? "uncertain"
          : delivery.state;
        await coordinator.markAttempting({ eventId: event.eventId, subscriptionKey: key });
      }
      let response = await transport(subscription, event.payload);
      let outcome = await applyDeliveryOutcome({
        kv: env.PUSH_SUBS,
        subscriptionKey: key,
        subscriptionKeys: storageKeys,
        response,
      });
      if (coordinator) {
        await coordinator.recordOutcome({ eventId: event.eventId, subscriptionKey: key, outcome });
      }
      if (outcome === "retryable") {
        const retryAcquired = coordinator
          ? await coordinator.acquireDelivery({
            eventId: event.eventId,
            subscriptionKey: key,
            automatic: true,
          })
          : { acquired: true };
        if (retryAcquired.acquired) {
          if (coordinator) await coordinator.markAttempting({ eventId: event.eventId, subscriptionKey: key });
          const retried = await retryDelivery({ outcome, attempt: 1, transport: () => transport(subscription, event.payload) });
          outcome = retried.outcome;
          response = retried.response || response;
          if (outcome === "gone") await deleteSubscriptionRecords(env.PUSH_SUBS, storageKeys || [key]);
          if (coordinator) {
            await coordinator.recordOutcome({ eventId: event.eventId, subscriptionKey: key, outcome });
          }
        }
      }
      return outcome;
    } catch {
      if (coordinator) {
        try {
          const current = await coordinator.getDelivery(event.eventId, key);
          if (current?.state === "attempting") {
            await coordinator.recordOutcome({
              eventId: event.eventId,
              subscriptionKey: key,
              outcome: "uncertain",
            });
          }
        } catch { /* the original delivery remains visibly unresolved */ }
      }
      return "uncertain";
    }
  });
  outcomes.push(...delivered);
  const summary = summarizeDeliveries(outcomes);
  const record = { ...acquired.record, state: summary.state, summary, updatedAt: nowFrom(env) };
  if (acquired.coordinator) {
    await acquired.coordinator.completeFanout({ eventId: event.eventId, summary });
  } else {
    await withBindingLock(env.PUSH_SUBS, acquired.key, () => env.PUSH_SUBS.put(
      acquired.key,
      JSON.stringify(record),
      { expirationTtl: 90 * 86_400 },
    ));
  }
  return jsonResponse({ eventId: event.eventId, ...summary, duplicate: false }, { headers: cors });
}

// Historical debug names remain private stubs for the legacy test loader. They
// are deliberately not routed by the production handler.
async function handleSendOne(_request, _env, cors) { return jsonResponse({ error: "not_found" }, { status: 404, headers: cors }); }
async function handleDebugStatus(_request, _env, cors) { return jsonResponse({ error: "not_found" }, { status: 404, headers: cors }); }
async function handleClearAll(_request, _env, cors) { return jsonResponse({ error: "not_found" }, { status: 404, headers: cors }); }

function derLength(length) {
  if (!Number.isInteger(length) || length < 0) throw new TypeError("DER length must be a non-negative integer");
  if (length < 128) return new Uint8Array([length]);
  const bytes = [];
  let remaining = length;
  while (remaining > 0) {
    bytes.unshift(remaining & 0xff);
    remaining = Math.floor(remaining / 256);
  }
  return new Uint8Array([0x80 | bytes.length, ...bytes]);
}

function derInteger(value) {
  if (!Number.isSafeInteger(value)) throw new TypeError("DER integer must be an integer");
  if (value < 0) throw new TypeError("DER integer cannot be negative");
  const bytes = [];
  let remaining = value;
  do {
    bytes.unshift(remaining & 0xff);
    remaining = Math.floor(remaining / 256);
  } while (remaining > 0);
  if (bytes[0] & 0x80) bytes.unshift(0);
  return concatBytes(new Uint8Array([0x02]), derLength(bytes.length), new Uint8Array(bytes));
}

function derValue(tag, content) {
  if (!(content instanceof Uint8Array)) throw new TypeError("DER content must be bytes");
  return concatBytes(new Uint8Array([tag]), derLength(content.length), content);
}

function derSequence(content) { return derValue(0x30, content); }
function derOctetString(content) { return derValue(0x04, content); }
function derBitString(content) { return derValue(0x03, content); }

function derTagged(tag, content) {
  if (!Number.isInteger(tag) || tag < 0 || tag > 30) throw new TypeError("DER tag is outside supported range");
  return derValue(0xa0 | tag, content);
}

function buildPkcs8PrivateKey(rawPrivateKey, rawPublicKey) {
  if (!(rawPrivateKey instanceof Uint8Array) || rawPrivateKey.length !== 32) {
    throw new TypeError("P-256 private key length must be 32 bytes");
  }
  if (!(rawPublicKey instanceof Uint8Array) || rawPublicKey.length !== 65 || rawPublicKey[0] !== 0x04) {
    throw new TypeError("P-256 public key length must be 65 bytes");
  }
  const curveOid = new Uint8Array([0x06, 0x08, 0x2a, 0x86, 0x48, 0xce, 0x3d, 0x03, 0x01, 0x07]);
  const publicBitString = derBitString(concatBytes(new Uint8Array([0x00]), rawPublicKey));
  const ecPrivateKey = derSequence(concatBytes(
    derInteger(1),
    derOctetString(rawPrivateKey),
    derTagged(0, curveOid),
    derTagged(1, publicBitString),
  ));
  const algorithm = derSequence(new Uint8Array([
    0x06, 0x07, 0x2a, 0x86, 0x48, 0xce, 0x3d, 0x02, 0x01,
    0x06, 0x08, 0x2a, 0x86, 0x48, 0xce, 0x3d, 0x03, 0x01, 0x07,
  ]));
  return derSequence(concatBytes(derInteger(0), algorithm, derOctetString(ecPrivateKey)));
}

async function hkdf(salt, ikm, info, length, options = {}) {
  if (!Number.isInteger(length) || length < 0 || length > 255 * 32) {
    throw new TypeError("HKDF length must be an integer no greater than 255 hash lengths");
  }
  if (![salt, ikm, info].every((value) => value instanceof Uint8Array)) throw new TypeError("HKDF inputs must be bytes");
  if (length === 0) return new Uint8Array();
  const cryptoApi = await runtimeCrypto(options.crypto);
  const actualSalt = salt.length ? salt : new Uint8Array(32);
  const extractKey = await cryptoApi.subtle.importKey("raw", actualSalt, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const prk = new Uint8Array(await cryptoApi.subtle.sign("HMAC", extractKey, ikm));
  const expandKey = await cryptoApi.subtle.importKey("raw", prk, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const blocks = [];
  let previous = new Uint8Array();
  let produced = 0;
  for (let counter = 1; produced < length; counter += 1) {
    previous = new Uint8Array(await cryptoApi.subtle.sign(
      "HMAC",
      expandKey,
      concatBytes(previous, info, new Uint8Array([counter])),
    ));
    blocks.push(previous);
    produced += previous.length;
  }
  return concatBytes(...blocks).slice(0, length);
}

function validateVapidSubject(subject) {
  if (typeof subject !== "string") return false;
  if (/^mailto:[^@\s]+@[^@\s]+$/i.test(subject)) return true;
  try {
    const url = new URL(subject);
    return url.protocol === "https:" && url.href === subject;
  } catch { return false; }
}

async function generateVapidHeaders(endpoint, subject, privateKeyBase64, publicKeyBase64, options = {}) {
  let endpointUrl;
  try { endpointUrl = new URL(endpoint); } catch { throw new TypeError("VAPID endpoint URL is invalid"); }
  if (endpointUrl.protocol !== "https:" || !endpointUrl.hostname || endpointUrl.username || endpointUrl.password) {
    throw new TypeError("VAPID endpoint must use HTTPS");
  }
  if (!validateVapidSubject(subject)) throw new TypeError("VAPID subject is invalid");
  let privateKey;
  let publicKey;
  try { privateKey = base64UrlDecode(privateKeyBase64); } catch { throw new TypeError("VAPID private key base64 is invalid"); }
  try { publicKey = base64UrlDecode(publicKeyBase64); } catch { throw new TypeError("VAPID public key base64 is invalid"); }
  if (privateKey.length !== 32) throw new TypeError("VAPID private key length must be 32 bytes");
  if (publicKey.length !== 65 || publicKey[0] !== 0x04) throw new TypeError("VAPID public key length must be 65 bytes");
  const cryptoApi = await runtimeCrypto(options.crypto);
  const now = Math.floor((typeof options.now === "function" ? options.now() : Date.now()) / 1_000);
  const header = base64UrlEncode(encoder.encode(JSON.stringify({ typ: "JWT", alg: "ES256" })));
  const claims = base64UrlEncode(encoder.encode(JSON.stringify({ aud: endpointUrl.origin, exp: now + 43_200, sub: subject })));
  const signingInput = `${header}.${claims}`;
  const imported = await cryptoApi.subtle.importKey(
    "pkcs8",
    buildPkcs8PrivateKey(privateKey, publicKey),
    { name: "ECDSA", namedCurve: "P-256" },
    false,
    ["sign"],
  );
  const signature = new Uint8Array(await cryptoApi.subtle.sign(
    { name: "ECDSA", hash: "SHA-256" },
    imported,
    encoder.encode(signingInput),
  ));
  return {
    Authorization: `vapid t=${signingInput}.${base64UrlEncode(signature)}, k=${base64UrlEncode(publicKey)}`,
  };
}

async function webPushEncrypt(payload, clientPublicKeyBase64, authBase64, options = {}) {
  if (typeof payload !== "string") throw new TypeError("push payload must be a string");
  const plaintext = encoder.encode(payload);
  if (plaintext.length > MAX_PUSH_PLAINTEXT_BYTES) throw new RangeError("push payload exceeds maximum 4096-byte record");
  let userAgentPublic;
  let authSecret;
  try { userAgentPublic = base64UrlDecode(clientPublicKeyBase64); } catch { throw new TypeError("client public key base64 is invalid"); }
  try { authSecret = base64UrlDecode(authBase64); } catch { throw new TypeError("auth base64 is invalid"); }
  if (userAgentPublic.length !== 65 || userAgentPublic[0] !== 0x04) throw new TypeError("client public key length must be 65 bytes");
  if (authSecret.length !== 16) throw new TypeError("auth secret length must be 16 bytes");
  const cryptoApi = await runtimeCrypto(options.crypto);
  const serverKeyPair = options.serverKeyPair || await cryptoApi.subtle.generateKey(
    { name: "ECDH", namedCurve: "P-256" },
    true,
    ["deriveBits"],
  );
  const salt = options.salt ? new Uint8Array(options.salt) : cryptoApi.getRandomValues(new Uint8Array(16));
  if (salt.length !== 16) throw new TypeError("salt length must be 16 bytes");
  const serverPublic = new Uint8Array(await cryptoApi.subtle.exportKey("raw", serverKeyPair.publicKey));
  const receiverKey = await cryptoApi.subtle.importKey(
    "raw",
    userAgentPublic,
    { name: "ECDH", namedCurve: "P-256" },
    true,
    [],
  );
  const sharedSecret = new Uint8Array(await cryptoApi.subtle.deriveBits(
    { name: "ECDH", public: receiverKey },
    serverKeyPair.privateKey,
    256,
  ));
  const keyInfo = concatBytes(encoder.encode("WebPush: info\0"), userAgentPublic, serverPublic);
  const ikm = await hkdf(authSecret, sharedSecret, keyInfo, 32, { crypto: cryptoApi });
  const cek = await hkdf(salt, ikm, encoder.encode("Content-Encoding: aes128gcm\0"), 16, { crypto: cryptoApi });
  const nonce = await hkdf(salt, ikm, encoder.encode("Content-Encoding: nonce\0"), 12, { crypto: cryptoApi });
  const record = concatBytes(plaintext, new Uint8Array([0x02]));
  const aesKey = await cryptoApi.subtle.importKey("raw", cek, { name: "AES-GCM" }, false, ["encrypt"]);
  const ciphertext = new Uint8Array(await cryptoApi.subtle.encrypt(
    { name: "AES-GCM", iv: nonce, tagLength: 128 },
    aesKey,
    record,
  ));
  const recordSize = Math.max(4_096, ciphertext.length);
  const header = new Uint8Array(21 + serverPublic.length);
  header.set(salt, 0);
  new DataView(header.buffer).setUint32(16, recordSize, false);
  header[20] = serverPublic.length;
  header.set(serverPublic, 21);
  return concatBytes(header, ciphertext);
}

async function recordDelivery(storage, input) {
  const key = deliveryKey(input.eventId, input.subscriptionKey);
  const record = {
    schemaVersion: SCHEMA_VERSION,
    eventId: input.eventId,
    subscriptionKey: input.subscriptionKey,
    outcome: input.outcome,
    attempt: Number.isInteger(input.attempt) ? input.attempt : 0,
    updatedAt: input.now,
  };
  await storage.put(key, record);
  return record;
}

async function purgeExpiredDeliveryRecords(storage, { cutoff, batchSize = DEFAULT_PAGE_SIZE } = {}) {
  if (!Number.isFinite(cutoff) || !Number.isInteger(batchSize) || batchSize <= 0) {
    throw new TypeError("cutoff and batchSize are required");
  }
  const candidates = [];
  const seen = new Set();
  let cursor;
  while (true) {
    const page = await storage.list({ prefix: "delivery:", cursor, limit: batchSize });
    for (const { name } of page.keys) {
      const raw = await storage.get(name);
      try {
        const record = typeof raw === "string" ? JSON.parse(raw) : raw;
        if (record && Number(record.updatedAt) < cutoff) candidates.push(name);
      } catch { /* malformed retention records are retained for audit */ }
    }
    if (page.list_complete) break;
    if (!page.cursor || seen.has(page.cursor)) throw new Error("retention cursor cycle detected");
    seen.add(page.cursor);
    cursor = page.cursor;
  }
  let deleted = 0;
  for (const key of candidates) {
    try {
      await storage.delete(key);
      deleted += 1;
    } catch (error) {
      error.cursor = key;
      error.deleted = deleted;
      throw error;
    }
  }
  return { deleted, complete: true, cursor: "" };
}

function notificationStorageKey(eventId) {
  return `notification:v${SCHEMA_VERSION}:${keyComponent(eventId)}`;
}

function deliveryStoragePrefix(eventId) {
  return `delivery:v${SCHEMA_VERSION}:${keyComponent(eventId)}:`;
}

async function storageValues(storage, prefix) {
  const listed = await storage.list({ prefix });
  if (listed instanceof Map) return [...listed.values()];
  const values = [];
  for (const { name } of listed.keys || []) {
    const value = await storage.get(name);
    if (value !== null) values.push(typeof value === "string" ? JSON.parse(value) : value);
  }
  return values;
}

async function finalizeNotification(storage, { eventId, expectedDeliveries, now }) {
  const key = notificationStorageKey(eventId);
  const existing = await storage.get(key);
  if (existing && ["complete", "uncertain", "partial"].includes(existing.state)) return existing;
  const deliveries = await storageValues(storage, deliveryStoragePrefix(eventId));
  const outcomes = deliveries.map((record) => record.state || record.outcome || "pending");
  const summary = summarizeDeliveries(outcomes.filter((value) => (
    ["delivered", "gone", "retryable", "uncertain", "invalid"].includes(value)
  )));
  const unresolved = outcomes.filter((value) => value === "pending" || value === "attempting").length;
  let state = summary.state;
  if (unresolved > 0 || deliveries.length < expectedDeliveries) state = "pending";
  const record = {
    ...(existing || { schemaVersion: SCHEMA_VERSION, eventId, createdAt: now }),
    ...summary,
    expectedDeliveries,
    state,
    updatedAt: now,
  };
  await storage.put(key, record);
  return record;
}

function conflict(message) { return new HttpError(409, message, "conflict"); }

export class NotificationCoordinator {
  constructor(state, env) {
    this.state = state;
    this.storage = state.storage;
    this.env = env;
    this.tail = Promise.resolve();
    if (typeof state.blockConcurrencyWhile === "function") state.blockConcurrencyWhile(async () => undefined);
  }

  now() { return nowFrom(this.env); }

  async exclusive(operation) {
    const previous = this.tail;
    let release;
    this.tail = new Promise((resolve) => { release = resolve; });
    await previous.catch(() => undefined);
    try { return await operation(); } finally { release(); }
  }

  async transaction(operation) {
    if (typeof this.storage.transaction === "function") return this.storage.transaction(operation);
    return operation(this.storage);
  }

  async acquireNotification(input) {
    return this.exclusive(() => this.transaction(async (storage) => {
      const key = notificationStorageKey(input.eventId);
      const existing = await storage.get(key);
      if (existing) {
        if (existing.payloadHash !== input.payloadHash) throw conflict("eventId payloadHash conflict");
        return { acquired: false, duplicate: true, state: existing.state, record: existing };
      }
      const timestamp = this.now();
      const record = {
        schemaVersion: SCHEMA_VERSION,
        eventId: input.eventId,
        payloadHash: input.payloadHash,
        state: "pending",
        createdAt: timestamp,
        updatedAt: timestamp,
      };
      await storage.put(key, record);
      if (input.failpoint === "after-insert") throw new Error("coordinator failpoint after-insert");
      return { acquired: true, duplicate: false, state: "pending", record };
    }));
  }

  async getNotification(eventId) {
    return (await this.storage.get(notificationStorageKey(eventId))) || null;
  }

  async getDelivery(eventId, subscriptionKeyValue) {
    return (await this.storage.get(deliveryKey(eventId, subscriptionKeyValue))) || null;
  }

  async acquireDelivery({ eventId, subscriptionKey: subKey, automatic = false }) {
    return this.exclusive(() => this.transaction(async (storage) => {
      const key = deliveryKey(eventId, subKey);
      const existing = await storage.get(key);
      if (!existing) {
        const timestamp = this.now();
        const record = {
          schemaVersion: SCHEMA_VERSION,
          eventId,
          subscriptionKey: subKey,
          state: "pending",
          attempts: 0,
          createdAt: timestamp,
          updatedAt: timestamp,
        };
        await storage.put(key, record);
        return { acquired: true, duplicate: false, state: "pending", attempt: 1 };
      }
      if (automatic && existing.state === "retryable" && existing.attempts < 2) {
        const record = { ...existing, state: "pending", updatedAt: this.now() };
        await storage.put(key, record);
        return { acquired: true, duplicate: false, state: "pending", attempt: existing.attempts + 1 };
      }
      return { acquired: false, duplicate: true, state: existing.state, attempt: existing.attempts };
    }));
  }

  async markAttempting({ eventId, subscriptionKey: subKey }) {
    return this.exclusive(() => this.transaction(async (storage) => {
      const key = deliveryKey(eventId, subKey);
      const existing = await storage.get(key);
      if (!existing || existing.state !== "pending") throw conflict("delivery transition must start from pending");
      const timestamp = this.now();
      const record = {
        ...existing,
        state: "attempting",
        attempts: existing.attempts + 1,
        attemptStartedAt: timestamp,
        updatedAt: timestamp,
      };
      await storage.put(key, record);
      return record;
    }));
  }

  async recordOutcome({ eventId, subscriptionKey: subKey, outcome }) {
    if (!["delivered", "gone", "retryable", "uncertain", "invalid"].includes(outcome)) {
      throw new HttpError(400, "invalid delivery outcome");
    }
    return this.exclusive(() => this.transaction(async (storage) => {
      const key = deliveryKey(eventId, subKey);
      const existing = await storage.get(key);
      const mayRecord = existing?.state === "attempting"
        || (existing?.state === "pending" && outcome === "retryable");
      if (!mayRecord) throw conflict("delivery outcome transition is out of order");
      const record = { ...existing, state: outcome, outcome, updatedAt: this.now() };
      delete record.attemptStartedAt;
      await storage.put(key, record);
      return record;
    }));
  }

  async recoverStaleAttempts({ olderThan }) {
    return this.exclusive(() => this.transaction(async (storage) => {
      const records = await storage.list({ prefix: "delivery:" });
      let recovered = 0;
      for (const [key, value] of records instanceof Map ? records.entries() : []) {
        if (value.state === "attempting" && value.attemptStartedAt < olderThan) {
          const record = { ...value, state: "uncertain", outcome: "uncertain", updatedAt: this.now() };
          delete record.attemptStartedAt;
          await storage.put(key, record);
          recovered += 1;
        }
      }
      return { recovered };
    }));
  }

  async resolveUncertain({ eventId, subscriptionKey: subKey, resolution, admin }) {
    if (!isPlainObject(admin) || typeof admin.subject !== "string" || !admin.subject
      || typeof admin.reason !== "string" || !admin.reason) {
      throw new HttpError(403, "admin authorization is required", "forbidden");
    }
    return this.exclusive(() => this.transaction(async (storage) => {
      const key = deliveryKey(eventId, subKey);
      const existing = await storage.get(key);
      if (!existing || existing.state !== "uncertain") throw conflict("delivery is not uncertain");
      const state = resolution === "retry" ? "retryable" : resolution;
      if (!["delivered", "gone", "invalid", "retryable"].includes(state)) {
        throw new HttpError(400, "invalid uncertain resolution");
      }
      const timestamp = this.now();
      const audit = [...(Array.isArray(existing.audit) ? existing.audit : []), {
        subject: admin.subject,
        reason: admin.reason,
        resolution,
        at: timestamp,
      }];
      const record = { ...existing, state, outcome: state, audit, updatedAt: timestamp };
      await storage.put(key, record);
      return record;
    }));
  }

  async finalize({ eventId, expectedDeliveries }) {
    return this.exclusive(() => this.transaction((storage) => finalizeNotification(storage, {
      eventId,
      expectedDeliveries,
      now: this.now(),
    })));
  }

  async completeFanout({ eventId, summary }) {
    return this.exclusive(() => this.transaction(async (storage) => {
      const key = notificationStorageKey(eventId);
      const existing = await storage.get(key);
      if (!existing) throw conflict("notification must be acquired before completion");
      if (existing.summary) return existing;
      const record = {
        ...existing,
        state: summary.state,
        summary: { ...summary },
        updatedAt: this.now(),
      };
      await storage.put(key, record);
      return record;
    }));
  }
}

function redactForLog(value) {
  const seen = new WeakSet();
  const sensitive = /^(?:authorization|body|endpoint|error|headers|keys|message|payload|providerbody|secret|stack|token)$/i;
  function visit(current, key = "") {
    if (sensitive.test(key)) return "[redacted]";
    if (current instanceof Error) return { name: current.name || "Error" };
    if (current === null || typeof current === "number" || typeof current === "boolean") return current;
    if (typeof current === "string") {
      if (/https?:\/\/|bearer\s|secret|token/i.test(current)) return "[redacted]";
      return current;
    }
    if (typeof current !== "object") return String(current);
    if (seen.has(current)) return "[Circular]";
    seen.add(current);
    if (Array.isArray(current)) return current.map((entry) => visit(entry));
    const result = {};
    for (const [childKey, child] of Object.entries(current)) {
      if (sensitive.test(childKey)) continue;
      result[childKey] = visit(child, childKey);
    }
    return result;
  }
  return visit(value);
}

async function workerFetch(request, env, ctx) {
  const path = new URL(request.url).pathname;
  const requestId = requestIdFor(request);
  const baseHeaders = { "X-Request-Id": requestId };
  const origin = request.headers.get("Origin");
  const originAllowed = validateOrigin(origin, allowedOrigins(env));
  const cors = originAllowed ? { ...corsHeaders(origin), ...baseHeaders } : baseHeaders;

  if (request.method === "OPTIONS") {
    if (!originAllowed) return forbidden(baseHeaders);
    return new Response(null, { status: 204, headers: cors });
  }
  const knownPost = path === "/api/subscribe/" || path === "/api/unsubscribe/" || path === "/api/send/";
  if (request.method !== "POST" || !knownPost) {
    return jsonResponse({ error: "not_found" }, { status: 404, headers: cors });
  }
  try {
    if (path === "/api/send/") {
      // Auth precedes parsing and optional browser-origin checks so credential
      // failures remain uniform and server-to-server delivery stays possible.
      if (!(await sendAuthorized(request, env))) return unauthorized(baseHeaders);
      if (origin && !originAllowed) return forbidden(baseHeaders);
      return await handleSend(request, env, cors);
    }
    if (!originAllowed) return forbidden(baseHeaders);
    if (!ctx || typeof ctx.waitUntil !== "function") throw new Error("execution context unavailable");
    if (path === "/api/subscribe/") return await handleSubscribe(request, env, cors, ctx);
    return await handleUnsubscribe(request, env, cors);
  } catch (error) {
    if (error instanceof HttpError) {
      return jsonResponse({ error: error.publicCode }, { status: error.status, headers: cors });
    }
    console.error(JSON.stringify(redactForLog({ event: "worker_error", requestId, error })));
    return jsonResponse({ error: "internal_error" }, { status: 500, headers: baseHeaders });
  }
}

export default {
  fetch: workerFetch,
};

// Pure helpers are exposed through a single explicit test seam. The legacy
// loader still instruments the three historical named exports below.
export const __test = {
  HttpError,
  NotificationCoordinator,
  applyDeliveryOutcome,
  base64UrlDecode,
  base64UrlEncode,
  buildNotificationPayload,
  buildPkcs8PrivateKey,
  buildWelcomePayload,
  classifyPushResponse,
  concatBytes,
  deliveryKey,
  derBitString,
  derInteger,
  derLength,
  derOctetString,
  derSequence,
  derTagged,
  enforceRateLimit,
  finalizeNotification,
  generateVapidHeaders,
  githubActionsTokenOk,
  hkdf,
  limitedConcurrency,
  listSubscriptionsPaginated,
  notificationKey,
  parseRequestBody,
  publicPostImage,
  purgeExpiredDeliveryRecords,
  recordDelivery,
  redactForLog,
  retryDelivery,
  subscriptionKey,
  summarizeDeliveries,
  tokenOk,
  validateNotificationEvent,
  validateOrigin,
  validateSubscription,
  webPushEncrypt,
};

export { webPushEncrypt, generateVapidHeaders, buildNotificationPayload };
