import { describe, expect, test as vitestTest } from "vitest";
import { webcrypto } from "node:crypto";

import { FakeKV, ExecutionContextRecorder, jsonRequest, validSubscription } from "./support/fake-worker-env.mjs";
import {
  loadWorkerTarget,
  requireFunction,
  workerHandler,
} from "./support/target-loader.mjs";
import { tracedTest } from "./support/trace-test.mjs";

const test = tracedTest(vitestTest);

const ORIGIN = "https://mragentes.com.ar";

function b64json(value) {
  return Buffer.from(JSON.stringify(value), "utf8").toString("base64url");
}

async function githubOidcToken(claims, privateKey) {
  const header = b64json({ alg: "RS256", kid: "worker-test-key", typ: "JWT" });
  const payload = b64json(claims);
  const signature = await webcrypto.subtle.sign(
    "RSASSA-PKCS1-v1_5",
    privateKey,
    new TextEncoder().encode(`${header}.${payload}`),
  );
  return `${header}.${payload}.${Buffer.from(signature).toString("base64url")}`;
}

async function targetFunction(name, traceId) {
  const target = await loadWorkerTarget(traceId);
  return { target, fn: requireFunction(target, name, traceId) };
}

function environment(overrides = {}) {
  return {
    PUSH_SUBS: new FakeKV(),
    API_TOKEN: "test-api-token-32-characters-long",
    ENVIRONMENT: "production",
    ALLOWED_ORIGINS: ORIGIN,
    ...overrides,
  };
}

describe("Worker authentication and routing contract", () => {
  test("[PUSH-AUTH-001] tokenOk acepta exclusivamente strings idénticos", async () => {
    const { fn } = await targetFunction("tokenOk", "PUSH-AUTH-001");
    expect(fn("same-secret", "same-secret")).toBe(true);
    expect(fn(new String("same-secret"), "same-secret")).toBe(false);
  });

  test("[PUSH-AUTH-002] tokenOk rechaza valores ausentes y tipos no string", async () => {
    const { fn } = await targetFunction("tokenOk", "PUSH-AUTH-002");
    for (const value of [undefined, null, 0, {}, [], true]) {
      expect(fn(value, "expected")).toBe(false);
      expect(fn("provided", value)).toBe(false);
    }
  });

  test("[PUSH-AUTH-003] tokenOk rechaza diferencias de cualquier posición con igual longitud", async () => {
    const { fn } = await targetFunction("tokenOk", "PUSH-AUTH-003");
    expect(fn("xbcdef", "abcdef")).toBe(false);
    expect(fn("abcxef", "abcdef")).toBe(false);
    expect(fn("abcdex", "abcdef")).toBe(false);
  });

  test("[PUSH-AUTH-004] tokenOk rechaza longitudes distintas y secretos vacíos", async () => {
    const { fn } = await targetFunction("tokenOk", "PUSH-AUTH-004");
    expect(fn("short", "longer")).toBe(false);
    expect(fn("longer", "short")).toBe(false);
    expect(fn("", "")).toBe(false);
  });

  test("[PUSH-AUTH-005] forbidden devuelve un error uniforme que no refleja credenciales", async () => {
    const { fn } = await targetFunction("forbidden", "PUSH-AUTH-005");
    const response = fn({ "X-Request-Id": "request-1" });
    expect(response.status).toBe(403);
    expect(response.headers.get("content-type")).toMatch(/^application\/json/);
    expect(await response.json()).toEqual({ error: "forbidden" });
    expect(await response.clone().text()).not.toContain("token");
  });

  test("[PUSH-AUTH-006] validateOrigin usa una allowlist exacta de origins HTTPS", async () => {
    const { fn } = await targetFunction("validateOrigin", "PUSH-AUTH-006");
    expect(fn(ORIGIN, [ORIGIN])).toBe(true);
    expect(fn(`${ORIGIN}.evil.test`, [ORIGIN])).toBe(false);
    expect(fn("http://mragentes.com.ar", [ORIGIN])).toBe(false);
    expect(fn("https://www.mragentes.com.ar", [ORIGIN])).toBe(false);
    expect(fn(null, [ORIGIN])).toBe(false);
  });

  test("[PUSH-AUTH-007] preflight sólo refleja un origin permitido y declara Vary Origin", async () => {
    const target = await loadWorkerTarget("PUSH-AUTH-007");
    const response = await workerHandler(target, "PUSH-AUTH-007").fetch(
      new Request("https://push.mragentes.test/api/subscribe/", {
        method: "OPTIONS",
        headers: { Origin: ORIGIN, "Access-Control-Request-Method": "POST" },
      }),
      environment(),
      new ExecutionContextRecorder(),
    );
    expect(response.status).toBe(204);
    expect(response.headers.get("access-control-allow-origin")).toBe(ORIGIN);
    expect(response.headers.get("vary")?.toLowerCase().split(/,\s*/)).toContain("origin");
  });

  test("[PUSH-AUTH-008] un origin no permitido recibe 403 sin CORS permisivo", async () => {
    const target = await loadWorkerTarget("PUSH-AUTH-008");
    const response = await workerHandler(target, "PUSH-AUTH-008").fetch(
      new Request("https://push.mragentes.test/api/subscribe/", {
        method: "OPTIONS",
        headers: { Origin: "https://mragentes.com.ar.evil.test" },
      }),
      environment(),
      new ExecutionContextRecorder(),
    );
    expect(response.status).toBe(403);
    expect(response.headers.get("access-control-allow-origin")).toBeNull();
  });

  test("[PUSH-AUTH-009] send autentica sólo con Authorization y nunca con token en JSON", async () => {
    const target = await loadWorkerTarget("PUSH-AUTH-009");
    const response = await workerHandler(target, "PUSH-AUTH-009").fetch(
      jsonRequest("https://push.mragentes.test/api/send/", {
        token: "test-api-token-32-characters-long",
        title: "Nota",
        body: "Nueva nota",
        url: `${ORIGIN}/notas/prueba/`,
        eventId: "note:2026-08-26:prueba",
      }),
      environment(),
      new ExecutionContextRecorder(),
    );
    expect(response.status).toBe(401);
  });

  test("[PUSH-AUTH-010] Authorization ausente, malformado o incorrecto produce la misma respuesta", async () => {
    const target = await loadWorkerTarget("PUSH-AUTH-010");
    const worker = workerHandler(target, "PUSH-AUTH-010");
    const variants = [undefined, "Token value", "Bearer", "Bearer wrong-secret"];
    const snapshots = [];
    for (const authorization of variants) {
      const headers = authorization ? { Authorization: authorization } : {};
      const response = await worker.fetch(
        jsonRequest("https://push.mragentes.test/api/send/", { body: "Nueva nota" }, { headers }),
        environment(),
        new ExecutionContextRecorder(),
      );
      snapshots.push({ status: response.status, body: await response.text() });
    }
    expect(new Set(snapshots.map(({ status }) => status))).toEqual(new Set([401]));
    expect(new Set(snapshots.map(({ body }) => body)).size).toBe(1);
  });

  test("[PUSH-AUTH-013] OIDC acepta sólo un token breve del repositorio autorizado", async () => {
    const { fn } = await targetFunction("githubActionsTokenOk", "PUSH-AUTH-013");
    const pair = await webcrypto.subtle.generateKey(
      { name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" },
      true,
      ["sign", "verify"],
    );
    const publicJwk = await webcrypto.subtle.exportKey("jwk", pair.publicKey);
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async () => new Response(JSON.stringify({
      keys: [{ ...publicJwk, kid: "worker-test-key", alg: "RS256" }],
    }), { status: 200, headers: { "Content-Type": "application/json" } });
    const now = Math.floor(Date.now() / 1000);
    const claims = {
      iss: "https://token.actions.githubusercontent.com",
      aud: "mragentes-push-notify",
      sub: "repo:RealLotex/mragentes-site:environment:cloudflare-production",
      repository: "RealLotex/mragentes-site",
      repository_id: "1270433781",
      ref: "refs/heads/main",
      environment: "cloudflare-production",
      workflow_ref: "RealLotex/mragentes-site/.github/workflows/notify-note.yml@refs/heads/main",
      iat: now,
      nbf: now - 1,
      exp: now + 120,
    };
    try {
      expect(await fn(await githubOidcToken(claims, pair.privateKey), environment())).toBe(true);
      expect(await fn(await githubOidcToken({ ...claims, repository_id: "0" }, pair.privateKey), environment())).toBe(false);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  test("[PUSH-AUTH-011] endpoints debug y clear-all son 404 en producción", async () => {
    const target = await loadWorkerTarget("PUSH-AUTH-011");
    const worker = workerHandler(target, "PUSH-AUTH-011");
    for (const [method, path] of [["GET", "/api/debug/status"], ["POST", "/api/debug/clear-all"], ["POST", "/api/send/one/"]]) {
      const response = await worker.fetch(
        new Request(`https://push.mragentes.test${path}`, {
          method,
          headers: { Authorization: "Bearer test-api-token-32-characters-long", "Content-Type": "application/json" },
          body: method === "GET" ? undefined : "{}",
        }),
        environment(),
        new ExecutionContextRecorder(),
      );
      expect(response.status, `${method} ${path}`).toBe(404);
    }
  });

  test("[PUSH-AUTH-012] errores internos incluyen request ID pero no stack, binding ni mensaje sensible", async () => {
    const target = await loadWorkerTarget("PUSH-AUTH-012");
    const kv = new FakeKV();
    kv.failNext("put", new Error("PUSH_SUBS secret binding exploded"));
    const response = await workerHandler(target, "PUSH-AUTH-012").fetch(
      jsonRequest("https://push.mragentes.test/api/subscribe/", validSubscription(
        "https://push.example.test/sub/1",
      ), { headers: { Origin: ORIGIN, "X-Request-Id": "req-auth-012" } }),
      environment({ PUSH_SUBS: kv }),
      new ExecutionContextRecorder(),
    );
    const text = await response.text();
    expect(response.status).toBe(500);
    expect(response.headers.get("x-request-id")).toBe("req-auth-012");
    expect(text).not.toMatch(/PUSH_SUBS|secret binding|stack/i);
  });
});

describe("Notification payload and image contract", () => {
  test("[PUSH-PAYLOAD-001] buildNotificationPayload aplica defaults completos y estables", async () => {
    const { fn } = await targetFunction("buildNotificationPayload", "PUSH-PAYLOAD-001");
    expect(fn({ eventId: "note:default" })).toEqual({
      title: "MR Agentes",
      body: "Hay contenido nuevo disponible.",
      url: `${ORIGIN}/`,
      icon: "/faviconhand512.png",
      badge: "/faviconhand512.png",
      tag: "note:default",
      eventId: "note:default",
    });
  });

  test("[PUSH-PAYLOAD-002] conserva Unicode válido sin cortar pares sustitutos", async () => {
    const { fn } = await targetFunction("buildNotificationPayload", "PUSH-PAYLOAD-002");
    const payload = fn({
      title: `${"á".repeat(118)}🧠fin`,
      body: `IA ${"x".repeat(248)}🧠final`,
      eventId: "note:unicode",
    });
    expect(payload.title).not.toMatch(/[\uD800-\uDBFF]$/);
    expect(payload.body).not.toMatch(/[\uD800-\uDBFF]$/);
    expect(new TextEncoder().encode(payload.title).length).toBeLessThanOrEqual(240);
    expect(new TextEncoder().encode(payload.body).length).toBeLessThanOrEqual(510);
  });

  test("[PUSH-PAYLOAD-003] URL de destino admite sólo notas del origin canónico", async () => {
    const { fn } = await targetFunction("buildNotificationPayload", "PUSH-PAYLOAD-003");
    expect(fn({ url: `${ORIGIN}/notas/nota-valida/`, eventId: "note:url" }).url).toBe(`${ORIGIN}/notas/nota-valida/`);
    for (const url of ["https://evil.test/notas/x/", `${ORIGIN}/servicios/`, "javascript:alert(1)", "//evil.test/notas/x/"]) {
      expect(() => fn({ url, eventId: "note:bad-url" }), url).toThrow(/url|origin|nota/i);
    }
  });

  test("[PUSH-PAYLOAD-004] publicPostImage acepta imagen stock same-origin con extensión permitida", async () => {
    const { fn } = await targetFunction("publicPostImage", "PUSH-PAYLOAD-004");
    expect(fn("/images/stock/robot.webp")).toBe(`${ORIGIN}/images/stock/robot.webp`);
    expect(fn(`${ORIGIN}/images/stock/caso-01.jpg`)).toBe(`${ORIGIN}/images/stock/caso-01.jpg`);
  });

  test("[PUSH-PAYLOAD-005] publicPostImage rechaza traversal normal, codificado y backslash", async () => {
    const { fn } = await targetFunction("publicPostImage", "PUSH-PAYLOAD-005");
    const attacks = [
      "/images/stock/../secret.webp",
      "/images/stock/%2e%2e/secret.webp",
      "/images/stock/%2e%2e%2fsecret.webp",
      "/images/stock/%252e%252e%252fsecret.webp",
      "/images/stock\\..\\secret.webp",
    ];
    for (const value of attacks) expect(fn(value), value).toBeNull();
  });

  test("[PUSH-PAYLOAD-006] publicPostImage rechaza protocolo, subdominio, userinfo y puerto alternos", async () => {
    const { fn } = await targetFunction("publicPostImage", "PUSH-PAYLOAD-006");
    const values = [
      "http://mragentes.com.ar/images/stock/a.webp",
      "https://cdn.mragentes.com.ar/images/stock/a.webp",
      "https://mragentes.com.ar.evil.test/images/stock/a.webp",
      "https://mragentes.com.ar@evil.test/images/stock/a.webp",
      "https://evil.test@mragentes.com.ar/images/stock/a.webp",
      "https://mragentes.com.ar:444/images/stock/a.webp",
      "data:image/png;base64,AAAA",
    ];
    for (const value of values) expect(fn(value), value).toBeNull();
  });

  test("[PUSH-PAYLOAD-007] publicPostImage rechaza query, fragmento y extensiones no allowlisted", async () => {
    const { fn } = await targetFunction("publicPostImage", "PUSH-PAYLOAD-007");
    for (const value of [
      "/images/stock/a.webp?token=secret",
      "/images/stock/a.webp#fragment",
      "/images/stock/a.svg",
      "/images/stock/a.html",
      "/images/stock/a",
      "/images/stock/a.webp.exe",
    ]) expect(fn(value), value).toBeNull();
  });

  test("[PUSH-PAYLOAD-008] tag y eventId son deterministas y derivan del evento editorial", async () => {
    const { fn } = await targetFunction("buildNotificationPayload", "PUSH-PAYLOAD-008");
    const input = {
      title: "Una nota",
      body: "Resumen",
      url: `${ORIGIN}/notas/una-nota/`,
      eventId: "blog-note:2026-08-26:una-nota",
    };
    const first = fn(input);
    const second = fn(input);
    expect(first.tag).toBe("blog-note:2026-08-26:una-nota");
    expect(first.eventId).toBe(input.eventId);
    expect(second).toEqual(first);
  });

  test("[PUSH-PAYLOAD-009] serialización JSON es estable independientemente del orden de input", async () => {
    const { fn } = await targetFunction("buildNotificationPayload", "PUSH-PAYLOAD-009");
    const left = fn({ title: "T", body: "B", url: `${ORIGIN}/notas/t/`, eventId: "note:t" });
    const right = fn({ eventId: "note:t", url: `${ORIGIN}/notas/t/`, body: "B", title: "T" });
    expect(JSON.stringify(left)).toBe(JSON.stringify(right));
  });

  test("[PUSH-PAYLOAD-010] icon y badge son rutas públicas de marca no sobreescribibles", async () => {
    const { fn } = await targetFunction("buildNotificationPayload", "PUSH-PAYLOAD-010");
    const result = fn({ icon: "https://evil.test/icon.png", badge: "data:image/png,x", eventId: "note:brand" });
    expect(result.icon).toBe("/faviconhand512.png");
    expect(result.badge).toBe("/faviconhand512.png");
  });

  test("[PUSH-PAYLOAD-011] input con campos extra o tipos estructurados se rechaza", async () => {
    const { fn } = await targetFunction("buildNotificationPayload", "PUSH-PAYLOAD-011");
    expect(() => fn({ title: { toString: () => "coerced" }, eventId: "note:object" })).toThrow(/title|schema|type/i);
    expect(() => fn({ title: "T", eventId: "note:extra", admin: true })).toThrow(/admin|extra|schema/i);
  });

  test("[PUSH-PAYLOAD-012] whitespace no cuenta como título, body, URL ni imagen válidos", async () => {
    const { fn } = await targetFunction("buildNotificationPayload", "PUSH-PAYLOAD-012");
    const result = fn({ title: "   ", body: "\n\t", url: " ", image: " ", eventId: "note:blank" });
    expect(result.title).toBe("MR Agentes");
    expect(result.body).toBe("Hay contenido nuevo disponible.");
    expect(result.url).toBe(`${ORIGIN}/`);
    expect(result).not.toHaveProperty("image");
  });

  test("[PUSH-PAYLOAD-013] parseRequestBody valida content-type, JSON objeto y body no vacío", async () => {
    const { fn } = await targetFunction("parseRequestBody", "PUSH-PAYLOAD-013");
    const ok = await fn(jsonRequest("https://push.test/api/send/", { body: "ok" }), { maxBytes: 256 });
    expect(ok).toEqual({ body: "ok" });
    for (const request of [
      new Request("https://push.test/api/send/", { method: "POST", body: "{}" }),
      new Request("https://push.test/api/send/", { method: "POST", headers: { "Content-Type": "text/plain" }, body: "{}" }),
      new Request("https://push.test/api/send/", { method: "POST", headers: { "Content-Type": "application/json" }, body: "" }),
      new Request("https://push.test/api/send/", { method: "POST", headers: { "Content-Type": "application/json" }, body: "[1]" }),
      new Request("https://push.test/api/send/", { method: "POST", headers: { "Content-Type": "application/json" }, body: "null" }),
      new Request("https://push.test/api/send/", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{" }),
    ]) await expect(fn(request, { maxBytes: 256 })).rejects.toMatchObject({ status: expect.any(Number) });
  });

  test("[PUSH-PAYLOAD-014] parseRequestBody limita content-length y streams chunked sin leer de más", async () => {
    const { fn } = await targetFunction("parseRequestBody", "PUSH-PAYLOAD-014");
    const declared = new Request("https://push.test/api/send/", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Content-Length": "999" },
      body: "{}",
    });
    await expect(fn(declared, { maxBytes: 32 })).rejects.toMatchObject({ status: 413 });

    let cancelled = false;
    const oversized = new Request("https://push.test/api/send/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: new ReadableStream({
        pull(controller) { controller.enqueue(new Uint8Array(64)); },
        cancel() { cancelled = true; },
      }),
      duplex: "half",
    });
    await expect(fn(oversized, { maxBytes: 32 })).rejects.toMatchObject({ status: 413 });
    expect(cancelled).toBe(true);
  });
});
