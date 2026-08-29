import { createHash } from "node:crypto";
import { describe, expect, test as vitestTest, vi } from "vitest";

import {
  ExecutionContextRecorder,
  FakeClock,
  FakeKV,
  jsonRequest,
  validSubscription,
} from "./support/fake-worker-env.mjs";
import {
  loadWorkerTarget,
  requireFunction,
  workerHandler,
} from "./support/target-loader.mjs";
import { tracedTest } from "./support/trace-test.mjs";

const test = tracedTest(vitestTest);

const SITE_ORIGIN = "https://mragentes.com.ar";
const WORKER_ORIGIN = "https://push.mragentes.test";
const API_TOKEN = "test-api-token-32-characters-long";

function env(kv = new FakeKV(), overrides = {}) {
  return {
    PUSH_SUBS: kv,
    API_TOKEN,
    ENVIRONMENT: "production",
    ALLOWED_ORIGINS: SITE_ORIGIN,
    ...overrides,
  };
}

function request(path, body, headers = {}) {
  return jsonRequest(`${WORKER_ORIGIN}${path}`, body, {
    headers: { Origin: SITE_ORIGIN, ...headers },
  });
}

async function exported(name, traceId) {
  const target = await loadWorkerTarget(traceId);
  return requireFunction(target, name, traceId);
}

describe("Push subscription validation and persistence", () => {
  test("[PUSH-SUB-001] validateSubscription normaliza una suscripción Web Push válida sin mutarla", async () => {
    const validate = await exported("validateSubscription", "PUSH-SUB-001");
    const input = validSubscription();
    const snapshot = structuredClone(input);
    const result = validate(input);
    expect(result).toEqual(snapshot);
    expect(input).toEqual(snapshot);
    expect(result).not.toBe(input);
  });

  test("[PUSH-SUB-002] validateSubscription exige endpoint HTTPS con host y longitud acotados", async () => {
    const validate = await exported("validateSubscription", "PUSH-SUB-002");
    for (const endpoint of [
      "http://push.example.test/sub/1",
      "ftp://push.example.test/sub/1",
      "https:///missing-host",
      "not-a-url",
      `https://push.example.test/${"x".repeat(2_049)}`,
      "https://user:pass@push.example.test/sub/1",
    ]) expect(() => validate(validSubscription(endpoint)), endpoint).toThrow(/endpoint|https|url|length/i);
  });

  test("[PUSH-SUB-003] validateSubscription exige p256dh y auth base64url canónicos de tamaño correcto", async () => {
    const validate = await exported("validateSubscription", "PUSH-SUB-003");
    const invalid = [
      { p256dh: "", auth: "BTBZMqHH6r4Tts7J_aSIgg" },
      { p256dh: "not+base64/url", auth: "BTBZMqHH6r4Tts7J_aSIgg" },
      { p256dh: "AQ", auth: "BTBZMqHH6r4Tts7J_aSIgg" },
      { p256dh: validSubscription().keys.p256dh, auth: "" },
      { p256dh: validSubscription().keys.p256dh, auth: "%%%%" },
      { p256dh: validSubscription().keys.p256dh, auth: "AQ" },
    ];
    for (const keys of invalid) {
      const value = validSubscription();
      value.keys = keys;
      expect(() => validate(value), JSON.stringify(keys)).toThrow(/p256dh|auth|key|base64|length/i);
    }
  });

  test("[PUSH-SUB-004] validateSubscription rechaza campos extra y prototipos peligrosos", async () => {
    const validate = await exported("validateSubscription", "PUSH-SUB-004");
    expect(() => validate({ ...validSubscription(), admin: true })).toThrow(/admin|extra|schema/i);
    expect(() => validate({ ...validSubscription(), keys: { ...validSubscription().keys, token: "secret" } })).toThrow(/token|extra|schema/i);
    const polluted = JSON.parse('{"endpoint":"https://push.example.test/x","keys":{"p256dh":"x","auth":"x"},"__proto__":{"admin":true}}');
    expect(() => validate(polluted)).toThrow(/schema|extra|proto/i);
  });

  test("[PUSH-SUB-005] subscriptionKey genera hash estable y nunca contiene el endpoint", async () => {
    const subscriptionKey = await exported("subscriptionKey", "PUSH-SUB-005");
    const endpoint = "https://push.example.test/private/user/123?token=sensitive";
    const first = await subscriptionKey(endpoint);
    const second = await subscriptionKey(endpoint);
    expect(first).toBe(second);
    expect(first).toMatch(/^sub:v\d+:[a-f0-9]{64}$/);
    expect(first).not.toContain("push.example.test");
    expect(first).not.toContain("sensitive");
    expect(first.endsWith(createHash("sha256").update(endpoint).digest("hex"))).toBe(true);
  });

  test("[PUSH-SUB-006] alta nueva persiste schema versionado bajo clave hasheada y TTL", async () => {
    const target = await loadWorkerTarget("PUSH-SUB-006");
    const kv = new FakeKV();
    const ctx = new ExecutionContextRecorder();
    const response = await workerHandler(target, "PUSH-SUB-006").fetch(
      request("/api/subscribe/", validSubscription()),
      env(kv),
      ctx,
    );
    expect(response.status).toBe(201);
    const put = kv.calls.find((call) => call.operation === "put");
    expect(put.key).toMatch(/^sub:v\d+:[a-f0-9]{64}$/);
    expect(put.key).not.toContain("push.example.test");
    expect(put.options.expirationTtl).toBeGreaterThanOrEqual(86_400);
    expect(JSON.parse(put.value)).toMatchObject({ schemaVersion: expect.any(Number), subscription: validSubscription() });
  });

  test("[PUSH-SUB-007] upsert idéntico conserva la alta y no programa otra bienvenida", async () => {
    const target = await loadWorkerTarget("PUSH-SUB-007");
    const kv = new FakeKV();
    const worker = workerHandler(target, "PUSH-SUB-007");
    const firstCtx = new ExecutionContextRecorder();
    const secondCtx = new ExecutionContextRecorder();
    const first = await worker.fetch(request("/api/subscribe/", validSubscription()), env(kv), firstCtx);
    const second = await worker.fetch(request("/api/subscribe/", validSubscription()), env(kv), secondCtx);
    expect(first.status).toBe(201);
    expect(second.status).toBe(200);
    expect((await second.json()).created).toBe(false);
    expect(secondCtx.promises).toHaveLength(0);

    const legacyKv = new FakeKV();
    const legacySubscription = validSubscription("https://legacy-push.example.test/subscription/existing");
    await legacyKv.put(
      legacySubscription.endpoint,
      JSON.stringify({ ...legacySubscription, revalidate: true }),
    );
    const legacyCtx = new ExecutionContextRecorder();
    const migrated = await worker.fetch(
      request("/api/subscribe/", legacySubscription),
      env(legacyKv),
      legacyCtx,
    );
    const migratedBody = await migrated.json();
    const canonicalWrites = legacyKv.calls.filter(
      (call) => call.operation === "put" && /^sub:v\d+:[a-f0-9]{64}$/.test(call.key),
    );
    expect(migrated.status).toBe(200);
    expect(migratedBody).toMatchObject({ created: false, welcomeScheduled: false });
    expect(legacyCtx.promises).toHaveLength(0);
    expect(canonicalWrites).toHaveLength(1);
    expect(JSON.parse(canonicalWrites[0].value).subscription).toEqual(legacySubscription);
    expect(await legacyKv.get(legacySubscription.endpoint)).toBeNull();
  });

  test("[PUSH-SUB-008] rotación de claves actualiza la misma clave sin duplicar suscripción", async () => {
    const target = await loadWorkerTarget("PUSH-SUB-008");
    const kv = new FakeKV();
    const worker = workerHandler(target, "PUSH-SUB-008");
    await worker.fetch(request("/api/subscribe/", validSubscription()), env(kv), new ExecutionContextRecorder());
    const rotated = validSubscription();
    rotated.keys.auth = "zTBZMqHH6r4Tts7J_aSIgg";
    const response = await worker.fetch(request("/api/subscribe/", rotated), env(kv), new ExecutionContextRecorder());
    const subPuts = kv.calls.filter((call) => call.operation === "put" && call.key.startsWith("sub:"));
    expect(response.status).toBe(200);
    expect(new Set(subPuts.map(({ key }) => key)).size).toBe(1);
    expect(JSON.parse(subPuts.at(-1).value).subscription.keys.auth).toBe(rotated.keys.auth);
  });

  test("[PUSH-SUB-009] re-registro por KV perdido se marca revalidation y no envía bienvenida", async () => {
    const target = await loadWorkerTarget("PUSH-SUB-009");
    const kv = new FakeKV();
    const ctx = new ExecutionContextRecorder();
    const response = await workerHandler(target, "PUSH-SUB-009").fetch(
      request("/api/subscribe/", { ...validSubscription(), revalidate: true }),
      env(kv),
      ctx,
    );
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ created: true, revalidated: true, welcomeScheduled: false });
    expect(ctx.promises).toHaveLength(0);
  });

  test("[PUSH-SUB-010] body inválido devuelve 400/413/415 sin escribir KV", async () => {
    const target = await loadWorkerTarget("PUSH-SUB-010");
    const kv = new FakeKV();
    const worker = workerHandler(target, "PUSH-SUB-010");
    const badRequests = [
      request("/api/subscribe/", {}),
      request("/api/subscribe/", { endpoint: "bad", keys: {} }),
      new Request(`${WORKER_ORIGIN}/api/subscribe/`, { method: "POST", headers: { Origin: SITE_ORIGIN, "Content-Type": "text/plain" }, body: "x" }),
    ];
    for (const badRequest of badRequests) {
      const response = await worker.fetch(badRequest, env(kv), new ExecutionContextRecorder());
      expect([400, 413, 415]).toContain(response.status);
    }
    expect(kv.calls.filter((call) => call.operation === "put")).toHaveLength(0);
  });

  test("[PUSH-SUB-011] rate limit permite el límite exacto y rechaza la siguiente alta", async () => {
    const target = await loadWorkerTarget("PUSH-SUB-011");
    const kv = new FakeKV();
    const worker = workerHandler(target, "PUSH-SUB-011");
    const statuses = [];
    for (let index = 0; index < 6; index += 1) {
      const sub = validSubscription(`https://push.example.test/sub/${index}`);
      const response = await worker.fetch(
        request("/api/subscribe/", sub, { "CF-Connecting-IP": "203.0.113.8" }),
        env(kv, { SUBSCRIBE_RATE_LIMIT: 5 }),
        new ExecutionContextRecorder(),
      );
      statuses.push(response.status);
    }
    expect(statuses.slice(0, 5).every((status) => status < 400)).toBe(true);
    expect(statuses[5]).toBe(429);
  });

  test("[PUSH-SUB-012] POST subscribe exige origin permitido incluso siendo endpoint público", async () => {
    const target = await loadWorkerTarget("PUSH-SUB-012");
    const response = await workerHandler(target, "PUSH-SUB-012").fetch(
      request("/api/subscribe/", validSubscription(), { Origin: "https://evil.test" }),
      env(),
      new ExecutionContextRecorder(),
    );
    expect(response.status).toBe(403);
  });

  test("[PUSH-SUB-013] fallo KV queda redactado y no dispara bienvenida", async () => {
    const target = await loadWorkerTarget("PUSH-SUB-013");
    const kv = new FakeKV();
    kv.failNext("get", new Error("endpoint=https://private.push.test/token"));
    const ctx = new ExecutionContextRecorder();
    const response = await workerHandler(target, "PUSH-SUB-013").fetch(
      request("/api/subscribe/", validSubscription()),
      env(kv),
      ctx,
    );
    expect(response.status).toBe(500);
    expect(await response.text()).not.toMatch(/private\.push|endpoint|token/i);
    expect(ctx.promises).toHaveLength(0);
  });

  test("[PUSH-SUB-014] bienvenida se entrega exclusivamente mediante ctx.waitUntil", async () => {
    const target = await loadWorkerTarget("PUSH-SUB-014");
    const ctx = new ExecutionContextRecorder();
    const response = await workerHandler(target, "PUSH-SUB-014").fetch(
      request("/api/subscribe/", validSubscription()),
      env(),
      ctx,
    );
    expect(response.status).toBe(201);
    expect(ctx.promises).toHaveLength(1);
    expect(await ctx.drain()).toHaveLength(1);
  });

  test("[PUSH-SUB-015] logs de alta no contienen endpoint, claves ni body", async () => {
    const logs = [];
    vi.spyOn(console, "log").mockImplementation((...values) => logs.push(values.join(" ")));
    vi.spyOn(console, "error").mockImplementation((...values) => logs.push(values.join(" ")));
    const target = await loadWorkerTarget("PUSH-SUB-015");
    await workerHandler(target, "PUSH-SUB-015").fetch(
      request("/api/subscribe/", validSubscription("https://push.example.test/private-token")),
      env(),
      new ExecutionContextRecorder(),
    );
    await Promise.resolve();
    const text = logs.join("\n");
    expect(text).not.toMatch(/private-token|p256dh|BTBZMqHH6r4Tts7J_aSIgg/);
  });

  test("[PUSH-SUB-016] TTL se renueva en upsert y nunca es cero, negativo ni mayor al máximo", async () => {
    const target = await loadWorkerTarget("PUSH-SUB-016");
    const clock = new FakeClock();
    const kv = new FakeKV({ clock });
    const worker = workerHandler(target, "PUSH-SUB-016");
    await worker.fetch(request("/api/subscribe/", validSubscription()), env(kv), new ExecutionContextRecorder());
    clock.advance(10 * 86_400_000);
    await worker.fetch(request("/api/subscribe/", validSubscription()), env(kv), new ExecutionContextRecorder());
    const ttls = kv.calls.filter((call) => call.operation === "put" && call.key.startsWith("sub:")).map((call) => call.options.expirationTtl);
    expect(ttls).toHaveLength(2);
    expect(ttls.every((ttl) => ttl >= 86_400 && ttl <= 31_536_000)).toBe(true);
  });

  test("[PUSH-SUB-017] dos altas concurrentes del mismo endpoint programan una sola bienvenida", async () => {
    const target = await loadWorkerTarget("PUSH-SUB-017");
    const kv = new FakeKV();
    const worker = workerHandler(target, "PUSH-SUB-017");
    const contexts = [new ExecutionContextRecorder(), new ExecutionContextRecorder()];
    const responses = await Promise.all(contexts.map((ctx) => worker.fetch(request("/api/subscribe/", validSubscription()), env(kv), ctx)));
    expect(responses.map(({ status }) => status).sort()).toEqual([200, 201]);
    expect(contexts.reduce((sum, ctx) => sum + ctx.promises.length, 0)).toBe(1);
  });

  test("[PUSH-SUB-018] respuesta diferencia alta, upsert y revalidación sin revelar claves", async () => {
    const target = await loadWorkerTarget("PUSH-SUB-018");
    const kv = new FakeKV();
    const worker = workerHandler(target, "PUSH-SUB-018");
    const first = await worker.fetch(request("/api/subscribe/", validSubscription()), env(kv), new ExecutionContextRecorder());
    const second = await worker.fetch(request("/api/subscribe/", validSubscription()), env(kv), new ExecutionContextRecorder());
    const firstText = await first.text();
    const secondText = await second.text();
    expect(JSON.parse(firstText)).toMatchObject({ created: true, welcomeScheduled: true });
    expect(JSON.parse(secondText)).toMatchObject({ created: false, welcomeScheduled: false });
    expect(firstText + secondText).not.toMatch(/p256dh|auth-secret|push\.example/);
  });
});

describe("Welcome notification lifecycle", () => {
  test("[PUSH-WELCOME-001] bienvenida usa el copy, branding y URL canónicos", async () => {
    const build = await exported("buildWelcomePayload", "PUSH-WELCOME-001");
    expect(build({ eventId: "welcome:subhash" })).toEqual({
      title: "🔔 Bienvenido a MR Agentes",
      body: "Activaste las notificaciones. Ahora vas a recibir alertas cuando publiquemos una nota nueva.",
      url: `${SITE_ORIGIN}/`,
      icon: "/faviconhand512.png",
      badge: "/faviconhand512.png",
      tag: "welcome:subhash",
      eventId: "welcome:subhash",
    });
  });

  test("[PUSH-WELCOME-002] 201/202 de push se registra como delivered", async () => {
    const classify = await exported("classifyPushResponse", "PUSH-WELCOME-002");
    expect(classify(new Response("", { status: 201 }))).toBe("delivered");
    expect(classify(new Response("", { status: 202 }))).toBe("delivered");
  });

  test("[PUSH-WELCOME-003] 404/410 de bienvenida marca gone y elimina sólo esa suscripción", async () => {
    const classify = await exported("classifyPushResponse", "PUSH-WELCOME-003");
    expect(classify(new Response("", { status: 404 }))).toBe("gone");
    expect(classify(new Response("", { status: 410 }))).toBe("gone");
  });

  test("[PUSH-WELCOME-004] 429 y 5xx de bienvenida son retryable con una tentativa acotada", async () => {
    const classify = await exported("classifyPushResponse", "PUSH-WELCOME-004");
    for (const status of [429, 500, 502, 503, 504]) {
      expect(classify(new Response("", { status })), String(status)).toBe("retryable");
    }
  });

  test("[PUSH-WELCOME-005] timeout, red y crypto desconocidos quedan uncertain", async () => {
    const classify = await exported("classifyPushResponse", "PUSH-WELCOME-005");
    for (const error of [new TypeError("network"), new DOMException("timeout", "TimeoutError"), new Error("crypto failed")]) {
      expect(classify(error), error.message).toBe("uncertain");
    }
  });

  test("[PUSH-WELCOME-006] fallo de bienvenida no revierte una suscripción ya persistida", async () => {
    const target = await loadWorkerTarget("PUSH-WELCOME-006");
    const kv = new FakeKV();
    const ctx = new ExecutionContextRecorder();
    const response = await workerHandler(target, "PUSH-WELCOME-006").fetch(
      request("/api/subscribe/", validSubscription()),
      env(kv, { PUSH_TRANSPORT: async () => { throw new Error("offline"); } }),
      ctx,
    );
    expect(response.status).toBe(201);
    await ctx.drain();
    expect(kv.calls.some((call) => call.operation === "put" && call.key.startsWith("sub:"))).toBe(true);
  });

  test("[PUSH-WELCOME-007] dedupe de bienvenida deriva de la clave hasheada de suscripción", async () => {
    const notificationKey = await exported("notificationKey", "PUSH-WELCOME-007");
    const first = notificationKey("welcome", "sub:v1:abc");
    const second = notificationKey("welcome", "sub:v1:abc");
    expect(first).toBe(second);
    expect(first).toMatch(/^notification:welcome:/);
    expect(first).not.toContain("https://");
  });

  test("[PUSH-WELCOME-008] revalidación silenciosa nunca crea evento welcome", async () => {
    const target = await loadWorkerTarget("PUSH-WELCOME-008");
    const kv = new FakeKV();
    const ctx = new ExecutionContextRecorder();
    await workerHandler(target, "PUSH-WELCOME-008").fetch(
      request("/api/subscribe/", { ...validSubscription(), revalidate: true }),
      env(kv),
      ctx,
    );
    expect(kv.calls.some((call) => call.operation === "put" && /welcome/.test(call.key))).toBe(false);
    expect(ctx.promises).toHaveLength(0);
  });

  test("[PUSH-WELCOME-009] bienvenida captura toda su vida async en waitUntil sin promesas flotantes", async () => {
    const target = await loadWorkerTarget("PUSH-WELCOME-009");
    const ctx = new ExecutionContextRecorder();
    await workerHandler(target, "PUSH-WELCOME-009").fetch(
      request("/api/subscribe/", validSubscription()),
      env(),
      ctx,
    );
    expect(ctx.promises).toHaveLength(1);
    const settled = await ctx.drain();
    expect(settled.every(({ status }) => status === "fulfilled")).toBe(true);
  });

  test("[PUSH-WELCOME-010] feedback de alta dice si la bienvenida quedó programada, no si ya se entregó", async () => {
    const target = await loadWorkerTarget("PUSH-WELCOME-010");
    const response = await workerHandler(target, "PUSH-WELCOME-010").fetch(
      request("/api/subscribe/", validSubscription()),
      env(),
      new ExecutionContextRecorder(),
    );
    const body = await response.json();
    expect(body).toMatchObject({ created: true, welcomeScheduled: true });
    expect(body).not.toHaveProperty("delivered");
  });
});

describe("Unsubscribe lifecycle", () => {
  test("[PUSH-UNSUB-001] body sin endpoint o con endpoint inválido devuelve 400", async () => {
    const target = await loadWorkerTarget("PUSH-UNSUB-001");
    const worker = workerHandler(target, "PUSH-UNSUB-001");
    for (const body of [{}, { endpoint: "bad" }, { endpoint: "http://push.example.test/x" }]) {
      const response = await worker.fetch(request("/api/unsubscribe/", body), env(), new ExecutionContextRecorder());
      expect(response.status).toBe(400);
    }
  });

  test("[PUSH-UNSUB-002] baja inexistente responde éxito idempotente sin crear estado", async () => {
    const target = await loadWorkerTarget("PUSH-UNSUB-002");
    const kv = new FakeKV();
    const response = await workerHandler(target, "PUSH-UNSUB-002").fetch(
      request("/api/unsubscribe/", { endpoint: validSubscription().endpoint }),
      env(kv),
      new ExecutionContextRecorder(),
    );
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ status: "ok", removed: false });
    expect(kv.calls.filter((call) => call.operation === "put")).toHaveLength(0);
  });

  test("[PUSH-UNSUB-003] baja existente elimina la clave hasheada correspondiente", async () => {
    const target = await loadWorkerTarget("PUSH-UNSUB-003");
    const kv = new FakeKV();
    const worker = workerHandler(target, "PUSH-UNSUB-003");
    await worker.fetch(request("/api/subscribe/", { ...validSubscription(), revalidate: true }), env(kv), new ExecutionContextRecorder());
    const storedKey = kv.calls.find((call) => call.operation === "put" && call.key.startsWith("sub:")).key;
    await kv.put(validSubscription().endpoint, JSON.stringify(validSubscription()));
    const response = await worker.fetch(request("/api/unsubscribe/", { endpoint: validSubscription().endpoint }), env(kv), new ExecutionContextRecorder());
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ removed: true });
    expect(kv.calls.some((call) => call.operation === "delete" && call.key === storedKey)).toBe(true);
    expect(await kv.get(storedKey)).toBeNull();
    expect(await kv.get(validSubscription().endpoint)).toBeNull();
  });

  test("[PUSH-UNSUB-004] repetir baja conserva status 200 y removed false", async () => {
    const target = await loadWorkerTarget("PUSH-UNSUB-004");
    const kv = new FakeKV();
    const worker = workerHandler(target, "PUSH-UNSUB-004");
    await worker.fetch(request("/api/unsubscribe/", { endpoint: validSubscription().endpoint }), env(kv), new ExecutionContextRecorder());
    const response = await worker.fetch(request("/api/unsubscribe/", { endpoint: validSubscription().endpoint }), env(kv), new ExecutionContextRecorder());
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ removed: false });
  });

  test("[PUSH-UNSUB-005] sólo el endpoint propio determina la clave; se rechazan selectors y admin flags", async () => {
    const target = await loadWorkerTarget("PUSH-UNSUB-005");
    for (const body of [
      { endpoint: validSubscription().endpoint, prefix: "sub:" },
      { endpoint: validSubscription().endpoint, all: true },
      { endpoint: validSubscription().endpoint, key: "sub:v1:other" },
    ]) {
      const response = await workerHandler(target, "PUSH-UNSUB-005").fetch(request("/api/unsubscribe/", body), env(), new ExecutionContextRecorder());
      expect(response.status).toBe(400);
    }
  });

  test("[PUSH-UNSUB-006] origin ajeno no puede dar de baja un endpoint", async () => {
    const target = await loadWorkerTarget("PUSH-UNSUB-006");
    const response = await workerHandler(target, "PUSH-UNSUB-006").fetch(
      request("/api/unsubscribe/", { endpoint: validSubscription().endpoint }, { Origin: "https://evil.test" }),
      env(),
      new ExecutionContextRecorder(),
    );
    expect(response.status).toBe(403);
  });

  test("[PUSH-UNSUB-007] fallo KV produce 500 genérico sin afirmar que la baja ocurrió", async () => {
    const target = await loadWorkerTarget("PUSH-UNSUB-007");
    const kv = new FakeKV();
    kv.failNext("get", new Error("private endpoint value"));
    const response = await workerHandler(target, "PUSH-UNSUB-007").fetch(
      request("/api/unsubscribe/", { endpoint: validSubscription().endpoint }),
      env(kv),
      new ExecutionContextRecorder(),
    );
    const text = await response.text();
    expect(response.status).toBe(500);
    expect(text).not.toMatch(/private endpoint|removed.*true/i);
  });

  test("[PUSH-UNSUB-008] respuesta y logs de baja no revelan endpoint ni hash interno", async () => {
    const logs = [];
    vi.spyOn(console, "log").mockImplementation((...values) => logs.push(values.join(" ")));
    const target = await loadWorkerTarget("PUSH-UNSUB-008");
    const endpoint = "https://push.example.test/private-user-token";
    const response = await workerHandler(target, "PUSH-UNSUB-008").fetch(
      request("/api/unsubscribe/", { endpoint }),
      env(),
      new ExecutionContextRecorder(),
    );
    const output = `${await response.text()}\n${logs.join("\n")}`;
    expect(output).not.toMatch(/private-user-token|sub:v\d+:[a-f0-9]{64}/);
  });

  test("[PUSH-UNSUB-009] dos bajas concurrentes son seguras y una sola reporta removed true", async () => {
    const target = await loadWorkerTarget("PUSH-UNSUB-009");
    const kv = new FakeKV();
    const worker = workerHandler(target, "PUSH-UNSUB-009");
    await worker.fetch(request("/api/subscribe/", { ...validSubscription(), revalidate: true }), env(kv), new ExecutionContextRecorder());
    const responses = await Promise.all([1, 2].map(() => worker.fetch(
      request("/api/unsubscribe/", { endpoint: validSubscription().endpoint }),
      env(kv),
      new ExecutionContextRecorder(),
    )));
    const bodies = await Promise.all(responses.map((response) => response.json()));
    expect(bodies.map(({ removed }) => removed).sort()).toEqual([false, true]);
  });

  test("[PUSH-UNSUB-010] rate limit de baja no comparte bucket global con altas", async () => {
    const enforce = await exported("enforceRateLimit", "PUSH-UNSUB-010");
    const store = new FakeKV();
    const clock = new FakeClock();
    for (let index = 0; index < 3; index += 1) {
      expect(await enforce(store, { bucket: "unsubscribe", identity: "ip-hash", limit: 3, windowSeconds: 60, now: clock.now() })).toMatchObject({ allowed: true });
    }
    expect(await enforce(store, { bucket: "unsubscribe", identity: "ip-hash", limit: 3, windowSeconds: 60, now: clock.now() })).toMatchObject({ allowed: false });
    expect(await enforce(store, { bucket: "subscribe", identity: "ip-hash", limit: 3, windowSeconds: 60, now: clock.now() })).toMatchObject({ allowed: true });
  });
});
