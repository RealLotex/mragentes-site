#!/usr/bin/env node
import assert from 'node:assert/strict';
import { webPushEncrypt, generateVapidHeaders, buildNotificationPayload, default as worker } from '../cf_worker.js';

const enc = new TextEncoder();
const b64 = (bytes) => Buffer.from(bytes).toString('base64url');
const unb64 = (value) => new Uint8Array(Buffer.from(value, 'base64url'));
const join = (...parts) => {
  const out = new Uint8Array(parts.reduce((n, part) => n + part.length, 0));
  let offset = 0;
  for (const part of parts) { out.set(part, offset); offset += part.length; }
  return out;
};

async function hkdf(salt, ikm, info, length) {
  const extractKey = await crypto.subtle.importKey('raw', salt, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const prk = new Uint8Array(await crypto.subtle.sign('HMAC', extractKey, ikm));
  const expandKey = await crypto.subtle.importKey('raw', prk, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  let t = new Uint8Array(0), output = new Uint8Array(0);
  for (let i = 1; output.length < length; i++) {
    t = new Uint8Array(await crypto.subtle.sign('HMAC', expandKey, join(t, info, new Uint8Array([i]))));
    output = join(output, t);
  }
  return output.slice(0, length);
}

async function decrypt(body, uaPrivateKey, uaPublic) {
  const salt = body.slice(0, 16);
  const view = new DataView(body.buffer, body.byteOffset, body.byteLength);
  const recordSize = view.getUint32(16, false);
  const idLength = body[20];
  const asPublic = body.slice(21, 21 + idLength);
  const ciphertext = body.slice(21 + idLength);
  assert.equal(idLength, 65);
  assert.ok(recordSize >= ciphertext.length);
  const asKey = await crypto.subtle.importKey('raw', asPublic, { name: 'ECDH', namedCurve: 'P-256' }, true, []);
  const shared = new Uint8Array(await crypto.subtle.deriveBits({ name: 'ECDH', public: asKey }, uaPrivateKey, 256));
  const ikm = await hkdf(unb64(TEST_AUTH), shared, join(enc.encode('WebPush: info\0'), uaPublic, asPublic), 32);
  const cek = await hkdf(salt, ikm, enc.encode('Content-Encoding: aes128gcm\0'), 16);
  const nonce = await hkdf(salt, ikm, enc.encode('Content-Encoding: nonce\0'), 12);
  const key = await crypto.subtle.importKey('raw', cek, { name: 'AES-GCM' }, false, ['decrypt']);
  return new Uint8Array(await crypto.subtle.decrypt({ name: 'AES-GCM', iv: nonce, tagLength: 128 }, key, ciphertext));
}

const TEST_AUTH = b64(crypto.getRandomValues(new Uint8Array(16)));

async function testRoundTrip() {
  const pair = await crypto.subtle.generateKey({ name: 'ECDH', namedCurve: 'P-256' }, true, ['deriveBits']);
  const publicKey = new Uint8Array(await crypto.subtle.exportKey('raw', pair.publicKey));
  const payload = JSON.stringify({ title: 'MR Agentes', body: 'Nota nueva publicada.' });
  const body = await webPushEncrypt(payload, b64(publicKey), TEST_AUTH);
  const record = await decrypt(body, pair.privateKey, publicKey);
  assert.equal(record.at(-1), 0x02);
  assert.equal(new TextDecoder().decode(record.slice(0, -1)), payload);
}

async function testRfcVector() {
  const uaPublic = unb64('BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4');
  const auth = unb64('BTBZMqHH6r4Tts7J_aSIgg');
  const asPublic = unb64('BP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A8');
  const asPrivate = unb64('yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw');
  const salt = unb64('DGv6ra1nlYgDCS1FRnbzlw');
  const privateKey = await crypto.subtle.importKey('jwk', {
    kty: 'EC', crv: 'P-256', d: b64(asPrivate), x: b64(asPublic.slice(1, 33)), y: b64(asPublic.slice(33)), ext: true,
  }, { name: 'ECDH', namedCurve: 'P-256' }, true, ['deriveBits']);
  const uaKey = await crypto.subtle.importKey('raw', uaPublic, { name: 'ECDH', namedCurve: 'P-256' }, true, []);
  const shared = new Uint8Array(await crypto.subtle.deriveBits({ name: 'ECDH', public: uaKey }, privateKey, 256));
  const ikm = await hkdf(auth, shared, join(enc.encode('WebPush: info\0'), uaPublic, asPublic), 32);
  const cek = await hkdf(salt, ikm, enc.encode('Content-Encoding: aes128gcm\0'), 16);
  const nonce = await hkdf(salt, ikm, enc.encode('Content-Encoding: nonce\0'), 12);
  const key = await crypto.subtle.importKey('raw', cek, { name: 'AES-GCM' }, false, ['encrypt']);
  const ciphertext = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv: nonce, tagLength: 128 }, key, join(enc.encode('When I grow up, I want to be a watermelon'), new Uint8Array([2]))));
  const header = new Uint8Array(86);
  header.set(salt); new DataView(header.buffer).setUint32(16, 4096); header[20] = 65; header.set(asPublic, 21);
  const expected = 'DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_yl95bQpu6cVPTpK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qu lcy4a-fN'.replace(' ', '');
  assert.equal(b64(join(header, ciphertext)), expected);
}

async function testVapid() {
  const pair = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify']);
  const privateJwk = await crypto.subtle.exportKey('jwk', pair.privateKey);
  const publicKey = b64(new Uint8Array(await crypto.subtle.exportKey('raw', pair.publicKey)));
  const headers = await generateVapidHeaders('https://fcm.googleapis.com/fcm/send/test', 'mailto:test@example.com', privateJwk.d, publicKey);
  assert.match(headers.Authorization, /^vapid t=[^,]+, k=.+$/);
}

async function testAuth() {
  const request = (path, body) => new Request('https://worker.test' + path, { method: 'POST', body: JSON.stringify(body), headers: { 'Content-Type': 'application/json' } });
  const env = { API_TOKEN: 'secret', PUSH_SUBS: { list: async () => ({ keys: [], list_complete: true }), delete: async () => {} } };
  for (const path of ['/api/send/', '/api/send/one/', '/api/debug/clear-all']) {
    const response = await worker.fetch(request(path, { body: 'test' }), env);
    assert.equal(response.status, 403, path);
  }
}

function testNotificationPayload() {
  const payload = buildNotificationPayload({
    title: 'Nota nueva',
    body: 'Entrá a leerla.',
    url: 'https://mragentes.com.ar/notas/nota-nueva/',
    image: 'https://mragentes.com.ar/images/stock/cover.jpg',
  });
  assert.equal(payload.icon, '/faviconhand512.png');
  assert.equal(payload.badge, '/faviconhand512.png');
  assert.equal(payload.image, 'https://mragentes.com.ar/images/stock/cover.jpg');

  const external = buildNotificationPayload({ image: 'https://tracker.example/pixel.jpg' });
  assert.equal('image' in external, false);
}

await testRoundTrip();
await testRfcVector();
await testVapid();
await testAuth();
testNotificationPayload();
console.log('push tests: ok');
