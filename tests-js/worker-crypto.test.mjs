import { webcrypto } from "node:crypto";
import { describe, expect, test as vitestTest, vi } from "vitest";

import { loadWorkerTarget, requireFunction } from "./support/target-loader.mjs";
import { tracedTest } from "./support/trace-test.mjs";

const test = tracedTest(vitestTest);

const encoder = new TextEncoder();
const decoder = new TextDecoder();

async function exported(name, traceId) {
  const target = await loadWorkerTarget(traceId);
  return requireFunction(target, name, traceId);
}

function hex(value) {
  return Uint8Array.from(Buffer.from(value.replaceAll(/\s/g, ""), "hex"));
}

function b64url(bytes) {
  return Buffer.from(bytes).toString("base64url");
}

async function receiverFixture() {
  const keyPair = await webcrypto.subtle.generateKey(
    { name: "ECDH", namedCurve: "P-256" },
    true,
    ["deriveBits"],
  );
  const publicRaw = new Uint8Array(await webcrypto.subtle.exportKey("raw", keyPair.publicKey));
  const auth = hex("00112233445566778899aabbccddeeff");
  return { keyPair, publicRaw, auth };
}

async function vapidFixture() {
  const keyPair = await webcrypto.subtle.generateKey(
    { name: "ECDSA", namedCurve: "P-256" },
    true,
    ["sign", "verify"],
  );
  const jwk = await webcrypto.subtle.exportKey("jwk", keyPair.privateKey);
  const publicRaw = new Uint8Array(await webcrypto.subtle.exportKey("raw", keyPair.publicKey));
  return {
    keyPair,
    privateRaw: Uint8Array.from(Buffer.from(jwk.d, "base64url")),
    publicRaw,
  };
}

async function decryptAes128Gcm(record, receiver, hkdf) {
  const bytes = new Uint8Array(record);
  const salt = bytes.slice(0, 16);
  const recordSize = new DataView(bytes.buffer, bytes.byteOffset + 16, 4).getUint32(0, false);
  const keyLength = bytes[20];
  const serverPublic = bytes.slice(21, 21 + keyLength);
  const ciphertext = bytes.slice(21 + keyLength);
  const serverKey = await webcrypto.subtle.importKey(
    "raw",
    serverPublic,
    { name: "ECDH", namedCurve: "P-256" },
    true,
    [],
  );
  const shared = new Uint8Array(await webcrypto.subtle.deriveBits(
    { name: "ECDH", public: serverKey },
    receiver.keyPair.privateKey,
    256,
  ));
  const keyInfo = concat(
    encoder.encode("WebPush: info\0"),
    receiver.publicRaw,
    serverPublic,
  );
  const ikm = await hkdf(receiver.auth, shared, keyInfo, 32);
  const cek = await hkdf(salt, ikm, encoder.encode("Content-Encoding: aes128gcm\0"), 16);
  const nonce = await hkdf(salt, ikm, encoder.encode("Content-Encoding: nonce\0"), 12);
  const aes = await webcrypto.subtle.importKey("raw", cek, { name: "AES-GCM" }, false, ["decrypt"]);
  const plaintext = new Uint8Array(await webcrypto.subtle.decrypt(
    { name: "AES-GCM", iv: nonce, tagLength: 128 },
    aes,
    ciphertext,
  ));
  return { plaintext, recordSize, salt, serverPublic, ciphertext };
}

function concat(...parts) {
  const result = new Uint8Array(parts.reduce((sum, part) => sum + part.length, 0));
  let offset = 0;
  for (const part of parts) {
    result.set(part, offset);
    offset += part.length;
  }
  return result;
}

describe("Web Push byte and base64 helpers", () => {
  test("[PUSH-CRYPTO-001] base64url round-trip cubre vacío y bytes binarios arbitrarios", async () => {
    const encode = await exported("base64UrlEncode", "PUSH-CRYPTO-001");
    const decode = await exported("base64UrlDecode", "PUSH-CRYPTO-001");
    for (const value of [new Uint8Array(), new Uint8Array([0]), new Uint8Array([0, 255, 128, 1]), Uint8Array.from({ length: 256 }, (_, index) => index)]) {
      expect(decode(encode(value))).toEqual(value);
    }
  });

  test("[PUSH-CRYPTO-002] decode acepta padding opcional pero encode siempre produce forma canónica", async () => {
    const encode = await exported("base64UrlEncode", "PUSH-CRYPTO-002");
    const decode = await exported("base64UrlDecode", "PUSH-CRYPTO-002");
    expect(decode("AQI")).toEqual(new Uint8Array([1, 2]));
    expect(decode("AQI=")).toEqual(new Uint8Array([1, 2]));
    expect(encode(new Uint8Array([1, 2]))).toBe("AQI");
    expect(encode(decode("AQI="))).toBe("AQI");
  });

  test("[PUSH-CRYPTO-003] decode rechaza alfabeto, padding y longitudes no canónicas", async () => {
    const decode = await exported("base64UrlDecode", "PUSH-CRYPTO-003");
    for (const value of ["a", "%%%", "AA+A", "AA/A", "AA===", "A A", "á", "AA\nAA"]) {
      expect(() => decode(value), value).toThrow(/base64|invalid|canonical|length/i);
    }
  });

  test("[PUSH-CRYPTO-004] concatBytes soporta 0/1/N partes y no muta inputs", async () => {
    const concatBytes = await exported("concatBytes", "PUSH-CRYPTO-004");
    expect(concatBytes()).toEqual(new Uint8Array());
    const left = new Uint8Array([1, 2]);
    const right = new Uint8Array([3, 4]);
    const result = concatBytes(left, right);
    expect(result).toEqual(new Uint8Array([1, 2, 3, 4]));
    result[0] = 99;
    expect(left).toEqual(new Uint8Array([1, 2]));
    expect(right).toEqual(new Uint8Array([3, 4]));
  });
});

describe("HKDF and DER helpers", () => {
  test("[PUSH-CRYPTO-005] hkdf coincide con RFC 5869 caso 1 SHA-256", async () => {
    const hkdf = await exported("hkdf", "PUSH-CRYPTO-005");
    const okm = await hkdf(
      hex("000102030405060708090a0b0c"),
      hex("0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b"),
      hex("f0f1f2f3f4f5f6f7f8f9"),
      42,
    );
    expect(Buffer.from(okm).toString("hex")).toBe("3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865");
  });

  test("[PUSH-CRYPTO-006] hkdf retorna exactamente longitudes 0, 1 y 32", async () => {
    const hkdf = await exported("hkdf", "PUSH-CRYPTO-006");
    for (const length of [0, 1, 32]) {
      const result = await hkdf(new Uint8Array(), new Uint8Array([1]), new Uint8Array(), length);
      expect(result).toBeInstanceOf(Uint8Array);
      expect(result).toHaveLength(length);
    }
  });

  test("[PUSH-CRYPTO-007] hkdf rechaza longitud negativa, no entera y mayor a 255 hashLen", async () => {
    const hkdf = await exported("hkdf", "PUSH-CRYPTO-007");
    for (const length of [-1, 1.5, Number.NaN, 255 * 32 + 1]) {
      await expect(hkdf(new Uint8Array(), new Uint8Array([1]), new Uint8Array(), length)).rejects.toThrow(/length|255|integer/i);
    }
  });

  test("[PUSH-CRYPTO-008] derLength codifica fronteras 0/127/128/255/256", async () => {
    const derLength = await exported("derLength", "PUSH-CRYPTO-008");
    expect(derLength(0)).toEqual(new Uint8Array([0x00]));
    expect(derLength(127)).toEqual(new Uint8Array([0x7f]));
    expect(derLength(128)).toEqual(new Uint8Array([0x81, 0x80]));
    expect(derLength(255)).toEqual(new Uint8Array([0x81, 0xff]));
    expect(derLength(256)).toEqual(new Uint8Array([0x82, 0x01, 0x00]));
    for (const invalid of [-1, 1.5, Number.NaN]) expect(() => derLength(invalid)).toThrow(/length|integer|positive/i);
  });

  test("[PUSH-CRYPTO-009] derInteger mantiene enteros positivos y padding para 128/255", async () => {
    const derInteger = await exported("derInteger", "PUSH-CRYPTO-009");
    expect(derInteger(0)).toEqual(new Uint8Array([0x02, 0x01, 0x00]));
    expect(derInteger(1)).toEqual(new Uint8Array([0x02, 0x01, 0x01]));
    expect(derInteger(127)).toEqual(new Uint8Array([0x02, 0x01, 0x7f]));
    expect(derInteger(128)).toEqual(new Uint8Array([0x02, 0x02, 0x00, 0x80]));
    expect(derInteger(255)).toEqual(new Uint8Array([0x02, 0x02, 0x00, 0xff]));
    expect(() => derInteger(-1)).toThrow(/negative|integer/i);
  });

  test("[PUSH-CRYPTO-010] sequence/octet/bit/tag usan DER corto y largo parseable", async () => {
    const target = await loadWorkerTarget("PUSH-CRYPTO-010");
    const sequence = requireFunction(target, "derSequence", "PUSH-CRYPTO-010");
    const octet = requireFunction(target, "derOctetString", "PUSH-CRYPTO-010");
    const bit = requireFunction(target, "derBitString", "PUSH-CRYPTO-010");
    const tagged = requireFunction(target, "derTagged", "PUSH-CRYPTO-010");
    for (const length of [0, 127, 128, 255, 256]) {
      const content = new Uint8Array(length);
      expect(sequence(content)[0]).toBe(0x30);
      expect(octet(content)[0]).toBe(0x04);
      expect(bit(content)[0]).toBe(0x03);
      expect(tagged(0, content)[0]).toBe(0xa0);
      expect(tagged(1, content)[0]).toBe(0xa1);
    }
    expect(() => tagged(31, new Uint8Array())).toThrow(/tag|range/i);
  });

  test("[PUSH-CRYPTO-011] buildPkcs8PrivateKey produce P-256 importable por WebCrypto", async () => {
    const build = await exported("buildPkcs8PrivateKey", "PUSH-CRYPTO-011");
    const vapid = await vapidFixture();
    const pkcs8 = build(vapid.privateRaw, vapid.publicRaw);
    const imported = await webcrypto.subtle.importKey(
      "pkcs8",
      pkcs8,
      { name: "ECDSA", namedCurve: "P-256" },
      false,
      ["sign"],
    );
    expect(imported.type).toBe("private");
    expect(imported.algorithm.namedCurve).toBe("P-256");
  });

  test("[PUSH-CRYPTO-012] buildPkcs8PrivateKey valida tamaños y no muta claves", async () => {
    const build = await exported("buildPkcs8PrivateKey", "PUSH-CRYPTO-012");
    const vapid = await vapidFixture();
    const privateSnapshot = vapid.privateRaw.slice();
    const publicSnapshot = vapid.publicRaw.slice();
    build(vapid.privateRaw, vapid.publicRaw);
    expect(vapid.privateRaw).toEqual(privateSnapshot);
    expect(vapid.publicRaw).toEqual(publicSnapshot);
    for (const [privateKey, publicKey] of [
      [new Uint8Array(0), vapid.publicRaw],
      [new Uint8Array(31), vapid.publicRaw],
      [new Uint8Array(33), vapid.publicRaw],
      [vapid.privateRaw, new Uint8Array(64)],
      [vapid.privateRaw, new Uint8Array(66)],
    ]) expect(() => build(privateKey, publicKey)).toThrow(/private|public|32|65|length/i);
  });
});

describe("VAPID and aes128gcm production crypto", () => {
  test("[PUSH-CRYPTO-013] VAPID JWT contiene aud exacto, sub y exp no mayor a 12h", async () => {
    const generate = await exported("generateVapidHeaders", "PUSH-CRYPTO-013");
    const vapid = await vapidFixture();
    vi.spyOn(Date, "now").mockReturnValue(Date.parse("2026-08-26T12:00:00Z"));
    const headers = await generate(
      "https://push.example.test/subscription/1",
      "mailto:admin@mragentes.com.ar",
      b64url(vapid.privateRaw),
      b64url(vapid.publicRaw),
      { now: () => Date.parse("2026-08-26T12:00:00Z") },
    );
    const jwt = headers.Authorization.match(/\bt=([^,\s]+)/)?.[1];
    expect(jwt).toBeTruthy();
    const [, encodedPayload] = jwt.split(".");
    const payload = JSON.parse(Buffer.from(encodedPayload, "base64url").toString("utf8"));
    expect(payload.aud).toBe("https://push.example.test");
    expect(payload.sub).toBe("mailto:admin@mragentes.com.ar");
    expect(payload.exp).toBeGreaterThan(Math.floor(Date.now() / 1_000));
    expect(payload.exp).toBeLessThanOrEqual(Math.floor(Date.now() / 1_000) + 43_200);
  });

  test("[PUSH-CRYPTO-014] firma VAPID ES256 es verificable y k es la pública canónica", async () => {
    const generate = await exported("generateVapidHeaders", "PUSH-CRYPTO-014");
    const vapid = await vapidFixture();
    const headers = await generate(
      "https://push.example.test/subscription/1",
      "mailto:admin@mragentes.com.ar",
      b64url(vapid.privateRaw),
      b64url(vapid.publicRaw),
    );
    const match = headers.Authorization.match(/^vapid t=([^,]+), k=([A-Za-z0-9_-]+)$/);
    expect(match).not.toBeNull();
    const [, jwt, publicKey] = match;
    const [header, payload, signature] = jwt.split(".");
    expect(JSON.parse(Buffer.from(header, "base64url").toString("utf8"))).toEqual({ typ: "JWT", alg: "ES256" });
    expect(publicKey).toBe(b64url(vapid.publicRaw));
    expect(await webcrypto.subtle.verify(
      { name: "ECDSA", hash: "SHA-256" },
      vapid.keyPair.publicKey,
      Buffer.from(signature, "base64url"),
      encoder.encode(`${header}.${payload}`),
    )).toBe(true);
  });

  test("[PUSH-CRYPTO-015] VAPID rechaza endpoint no HTTPS, subject y claves inválidos", async () => {
    const generate = await exported("generateVapidHeaders", "PUSH-CRYPTO-015");
    const vapid = await vapidFixture();
    const validPrivate = b64url(vapid.privateRaw);
    const validPublic = b64url(vapid.publicRaw);
    for (const args of [
      ["http://push.example.test/x", "mailto:a@example.test", validPrivate, validPublic],
      ["not-url", "mailto:a@example.test", validPrivate, validPublic],
      ["https://push.example.test/x", "not-a-subject", validPrivate, validPublic],
      ["https://push.example.test/x", "mailto:a@example.test", "bad", validPublic],
      ["https://push.example.test/x", "mailto:a@example.test", validPrivate, "bad"],
    ]) await expect(generate(...args)).rejects.toThrow(/https|endpoint|subject|key|base64|length/i);
  });

  test("[PUSH-CRYPTO-016] webPushEncrypt hace round-trip sobre el record productivo", async () => {
    const encrypt = await exported("webPushEncrypt", "PUSH-CRYPTO-016");
    const hkdf = await exported("hkdf", "PUSH-CRYPTO-016");
    const receiver = await receiverFixture();
    const encrypted = await encrypt(
      "Mensaje Web Push 🧠",
      b64url(receiver.publicRaw),
      b64url(receiver.auth),
      { crypto: webcrypto },
    );
    const decoded = await decryptAes128Gcm(encrypted, receiver, hkdf);
    expect(decoded.recordSize).toBeGreaterThanOrEqual(decoded.ciphertext.length);
    expect(decoded.plaintext.at(-1)).toBe(0x02);
    expect(decoder.decode(decoded.plaintext.slice(0, -1))).toBe("Mensaje Web Push 🧠");
  });

  test("[PUSH-CRYPTO-017] webPushEncrypt acepta 0/máximo y rechaza exceso o claves inválidas", async () => {
    const encrypt = await exported("webPushEncrypt", "PUSH-CRYPTO-017");
    const receiver = await receiverFixture();
    await expect(encrypt("", b64url(receiver.publicRaw), b64url(receiver.auth), { crypto: webcrypto })).resolves.toBeInstanceOf(Uint8Array);
    await expect(encrypt("x".repeat(3_993), b64url(receiver.publicRaw), b64url(receiver.auth), { crypto: webcrypto })).resolves.toBeInstanceOf(Uint8Array);
    await expect(encrypt("x".repeat(3_994), b64url(receiver.publicRaw), b64url(receiver.auth), { crypto: webcrypto })).rejects.toThrow(/payload|maximum|4096/i);
    for (const [publicKey, auth] of [["bad", b64url(receiver.auth)], [b64url(receiver.publicRaw), "bad"], ["", ""]]) {
      await expect(encrypt("x", publicKey, auth, { crypto: webcrypto })).rejects.toThrow(/key|auth|base64|length/i);
    }
  });

  test("[PUSH-CRYPTO-018] salt/ECDH inyectados hacen vector determinista y otro salt cambia ciphertext", async () => {
    const encrypt = await exported("webPushEncrypt", "PUSH-CRYPTO-018");
    const receiver = await receiverFixture();
    const serverKeyPair = await webcrypto.subtle.generateKey(
      { name: "ECDH", namedCurve: "P-256" },
      true,
      ["deriveBits"],
    );
    const common = {
      crypto: webcrypto,
      serverKeyPair,
      salt: hex("000102030405060708090a0b0c0d0e0f"),
    };
    const first = await encrypt("deterministic", b64url(receiver.publicRaw), b64url(receiver.auth), common);
    const second = await encrypt("deterministic", b64url(receiver.publicRaw), b64url(receiver.auth), common);
    const changed = await encrypt("deterministic", b64url(receiver.publicRaw), b64url(receiver.auth), {
      ...common,
      salt: hex("101112131415161718191a1b1c1d1e1f"),
    });
    expect(first).toEqual(second);
    expect(changed).not.toEqual(first);
  });
});
