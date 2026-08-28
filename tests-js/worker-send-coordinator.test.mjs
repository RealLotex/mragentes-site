import { describe, expect, test as vitestTest, vi } from "vitest";

import {
  ExecutionContextRecorder,
  FakeClock,
  FakeDurableObjectState,
  FakeDurableStorage,
  FakeKV,
  FetchRouter,
  jsonRequest,
  validSubscription,
} from "./support/fake-worker-env.mjs";
import {
  loadWorkerTarget,
  requireExport,
  requireFunction,
  workerHandler,
} from "./support/target-loader.mjs";
import { tracedTest } from "./support/trace-test.mjs";

const test = tracedTest(vitestTest);

const SITE_ORIGIN = "https://mragentes.com.ar";
const WORKER_ORIGIN = "https://push.mragentes.test";
const TOKEN = "send-contract-token-32-characters";
const FIXED_NOW = Date.parse("2026-08-26T12:00:00.000Z");

async function exported(name, traceId) {
  const target = await loadWorkerTarget(traceId);
  return requireFunction(target, name, traceId);
}

async function makeCoordinator(traceId, storage = new FakeDurableStorage()) {
  const target = await loadWorkerTarget(traceId);
  const Coordinator = requireExport(target, "NotificationCoordinator", traceId);
  expect(typeof Coordinator).toBe("function");
  const state = new FakeDurableObjectState(storage);
  const instance = new Coordinator(state, { CLOCK: () => FIXED_NOW });
  await Promise.all(state.blockConcurrencyWhileCalls);
  return { instance, storage, state };
}

function notification(overrides = {}) {
  return {
    eventId: "blog-note:2026-08-26:ia-segura",
    payloadHash: "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    payload: {
      title: "IA segura",
      body: "Nueva nota disponible",
      url: `${SITE_ORIGIN}/notas/ia-segura/`,
      image: `${SITE_ORIGIN}/images/stock/ia-segura.webp`,
    },
    ...overrides,
  };
}

function pushEnvironment(kv = new FakeKV(), overrides = {}) {
  return {
    PUSH_SUBS: kv,
    API_TOKEN: TOKEN,
    ALLOWED_ORIGINS: SITE_ORIGIN,
    ENVIRONMENT: "production",
    CLOCK: () => FIXED_NOW,
    ...overrides,
  };
}

function sendRequest(body = notification(), headers = {}) {
  return jsonRequest(`${WORKER_ORIGIN}/api/send/`, body, {
    headers: {
      Origin: SITE_ORIGIN,
      Authorization: `Bearer ${TOKEN}`,
      "Idempotency-Key": body.eventId,
      ...headers,
    },
  });
}

async function seedSubscriptions(kv, count) {
  for (let index = 0; index < count; index += 1) {
    await kv.put(
      `sub:v1:${String(index).padStart(64, "0")}`,
      JSON.stringify({
        schemaVersion: 1,
        subscription: validSubscription(`https://push-${index}.example.test/subscription`),
      }),
    );
  }
}

describe("Durable Object notification coordinator", () => {
  test("[PUSH-COORD-001] primera adquisición crea evento pending y devuelve acquired", async () => {
    const { instance } = await makeCoordinator("PUSH-COORD-001");
    const result = await instance.acquireNotification(notification());
    expect(result).toMatchObject({ acquired: true, duplicate: false, state: "pending" });
  });

  test("[PUSH-COORD-002] mismo eventId y payloadHash es dedupe, no nueva adquisición", async () => {
    const { instance } = await makeCoordinator("PUSH-COORD-002");
    await instance.acquireNotification(notification());
    const second = await instance.acquireNotification(notification());
    expect(second).toMatchObject({ acquired: false, duplicate: true });
  });

  test("[PUSH-COORD-003] mismo eventId con hash distinto es conflicto 409", async () => {
    const { instance } = await makeCoordinator("PUSH-COORD-003");
    await instance.acquireNotification(notification());
    await expect(instance.acquireNotification(notification({ payloadHash: "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" })))
      .rejects.toMatchObject({ status: 409 });
  });

  test("[PUSH-COORD-004] adquisiciones seriales de eventos distintos conservan ambos estados", async () => {
    const { instance } = await makeCoordinator("PUSH-COORD-004");
    await instance.acquireNotification(notification());
    await instance.acquireNotification(notification({ eventId: "blog-note:2026-08-30:segunda" }));
    expect(await instance.getNotification(notification().eventId)).toMatchObject({ state: "pending" });
    expect(await instance.getNotification("blog-note:2026-08-30:segunda")).toMatchObject({ state: "pending" });
  });

  test("[PUSH-COORD-005] dos adquisiciones concurrentes del mismo evento producen un único owner", async () => {
    const { instance } = await makeCoordinator("PUSH-COORD-005");
    const results = await Promise.all([
      instance.acquireNotification(notification()),
      instance.acquireNotification(notification()),
    ]);
    expect(results.filter(({ acquired }) => acquired)).toHaveLength(1);
    expect(results.filter(({ duplicate }) => duplicate)).toHaveLength(1);
  });

  test("[PUSH-COORD-006] evento complete no se readquiere en re-run", async () => {
    const { instance } = await makeCoordinator("PUSH-COORD-006");
    await instance.acquireNotification(notification());
    await instance.finalize({ eventId: notification().eventId, expectedDeliveries: 0 });
    expect(await instance.acquireNotification(notification())).toMatchObject({ acquired: false, duplicate: true, state: "complete" });
  });

  test("[PUSH-COORD-007] evento partial permite sólo entregas retryable pendientes", async () => {
    const { instance } = await makeCoordinator("PUSH-COORD-007");
    await instance.acquireNotification(notification());
    await instance.acquireDelivery({ eventId: notification().eventId, subscriptionKey: "sub:v1:a" });
    await instance.recordOutcome({ eventId: notification().eventId, subscriptionKey: "sub:v1:a", outcome: "retryable" });
    await instance.finalize({ eventId: notification().eventId, expectedDeliveries: 1 });
    const state = await instance.getNotification(notification().eventId);
    expect(state.state).toBe("partial");
    expect(state.retryable).toBe(1);
  });

  test("[PUSH-COORD-008] evento uncertain nunca se reenvía automáticamente", async () => {
    const { instance } = await makeCoordinator("PUSH-COORD-008");
    await instance.acquireNotification(notification());
    await instance.acquireDelivery({ eventId: notification().eventId, subscriptionKey: "sub:v1:a" });
    await instance.markAttempting({ eventId: notification().eventId, subscriptionKey: "sub:v1:a" });
    await instance.recordOutcome({ eventId: notification().eventId, subscriptionKey: "sub:v1:a", outcome: "uncertain" });
    await instance.finalize({ eventId: notification().eventId, expectedDeliveries: 1 });
    expect(await instance.acquireDelivery({ eventId: notification().eventId, subscriptionKey: "sub:v1:a", automatic: true }))
      .toMatchObject({ acquired: false, state: "uncertain" });
  });

  test("[PUSH-COORD-009] estado persiste al construir otra instancia con el mismo storage", async () => {
    const storage = new FakeDurableStorage();
    const first = await makeCoordinator("PUSH-COORD-009", storage);
    await first.instance.acquireNotification(notification());
    const second = await makeCoordinator("PUSH-COORD-009", storage);
    expect(await second.instance.getNotification(notification().eventId)).toMatchObject({ payloadHash: notification().payloadHash, state: "pending" });
  });

  test("[PUSH-COORD-010] acquireDelivery crea una sola entrega pending por suscripción", async () => {
    const { instance } = await makeCoordinator("PUSH-COORD-010");
    await instance.acquireNotification(notification());
    const first = await instance.acquireDelivery({ eventId: notification().eventId, subscriptionKey: "sub:v1:a" });
    const second = await instance.acquireDelivery({ eventId: notification().eventId, subscriptionKey: "sub:v1:a" });
    expect(first).toMatchObject({ acquired: true, state: "pending" });
    expect(second).toMatchObject({ acquired: false, duplicate: true });
  });

  test("[PUSH-COORD-011] transiciones de entrega usan compare-and-set y rechazan orden inválido", async () => {
    const { instance } = await makeCoordinator("PUSH-COORD-011");
    await instance.acquireNotification(notification());
    await instance.acquireDelivery({ eventId: notification().eventId, subscriptionKey: "sub:v1:a" });
    await expect(instance.recordOutcome({ eventId: notification().eventId, subscriptionKey: "sub:v1:a", outcome: "delivered" }))
      .rejects.toMatchObject({ status: 409 });
    await instance.markAttempting({ eventId: notification().eventId, subscriptionKey: "sub:v1:a" });
    await instance.recordOutcome({ eventId: notification().eventId, subscriptionKey: "sub:v1:a", outcome: "delivered" });
    await expect(instance.recordOutcome({ eventId: notification().eventId, subscriptionKey: "sub:v1:a", outcome: "gone" }))
      .rejects.toMatchObject({ status: 409 });
  });

  test("[PUSH-COORD-012] una entrega retryable obtiene como máximo una tentativa automática adicional", async () => {
    const { instance } = await makeCoordinator("PUSH-COORD-012");
    await instance.acquireNotification(notification());
    await instance.acquireDelivery({ eventId: notification().eventId, subscriptionKey: "sub:v1:a" });
    await instance.markAttempting({ eventId: notification().eventId, subscriptionKey: "sub:v1:a" });
    await instance.recordOutcome({ eventId: notification().eventId, subscriptionKey: "sub:v1:a", outcome: "retryable" });
    expect(await instance.acquireDelivery({ eventId: notification().eventId, subscriptionKey: "sub:v1:a", automatic: true })).toMatchObject({ acquired: true, attempt: 2 });
    await instance.markAttempting({ eventId: notification().eventId, subscriptionKey: "sub:v1:a" });
    await instance.recordOutcome({ eventId: notification().eventId, subscriptionKey: "sub:v1:a", outcome: "retryable" });
    expect(await instance.acquireDelivery({ eventId: notification().eventId, subscriptionKey: "sub:v1:a", automatic: true })).toMatchObject({ acquired: false });
  });

  test("[PUSH-COORD-013] crash antes de fetch deja pending reanudable sin consumir tentativa", async () => {
    const { instance } = await makeCoordinator("PUSH-COORD-013");
    await instance.acquireNotification(notification());
    await instance.acquireDelivery({ eventId: notification().eventId, subscriptionKey: "sub:v1:a" });
    const state = await instance.getDelivery(notification().eventId, "sub:v1:a");
    expect(state).toMatchObject({ state: "pending", attempts: 0 });
  });

  test("[PUSH-COORD-014] crash después de iniciar fetch queda uncertain tras recovery", async () => {
    const { instance } = await makeCoordinator("PUSH-COORD-014");
    await instance.acquireNotification(notification());
    await instance.acquireDelivery({ eventId: notification().eventId, subscriptionKey: "sub:v1:a" });
    await instance.markAttempting({ eventId: notification().eventId, subscriptionKey: "sub:v1:a" });
    await instance.recoverStaleAttempts({ olderThan: FIXED_NOW + 1 });
    expect(await instance.getDelivery(notification().eventId, "sub:v1:a")).toMatchObject({ state: "uncertain" });
  });

  test("[PUSH-COORD-015] resolución manual de uncertain exige admin y deja auditoría", async () => {
    const { instance } = await makeCoordinator("PUSH-COORD-015");
    await instance.acquireNotification(notification());
    await instance.acquireDelivery({ eventId: notification().eventId, subscriptionKey: "sub:v1:a" });
    await instance.markAttempting({ eventId: notification().eventId, subscriptionKey: "sub:v1:a" });
    await instance.recoverStaleAttempts({ olderThan: FIXED_NOW + 1 });
    await expect(instance.resolveUncertain({ eventId: notification().eventId, subscriptionKey: "sub:v1:a", resolution: "retry" }))
      .rejects.toMatchObject({ status: 403 });
    await instance.resolveUncertain({
      eventId: notification().eventId,
      subscriptionKey: "sub:v1:a",
      resolution: "delivered",
      admin: { subject: "operator:test", reason: "provider confirmation" },
    });
    expect(await instance.getDelivery(notification().eventId, "sub:v1:a")).toMatchObject({
      state: "delivered",
      audit: expect.arrayContaining([expect.objectContaining({ subject: "operator:test", reason: "provider confirmation" })]),
    });
  });

  test("[PUSH-COORD-016] error dentro de transacción no deja estado parcialmente escrito", async () => {
    const storage = new FakeDurableStorage();
    const { instance } = await makeCoordinator("PUSH-COORD-016", storage);
    await expect(instance.acquireNotification(notification({ failpoint: "after-insert" }))).rejects.toThrow();
    expect(await instance.getNotification(notification().eventId)).toBeNull();
  });
});

describe("Send fan-out and idempotency", () => {
  test("[PUSH-SEND-001] send exige Bearer válido aunque el body contenga token legacy", async () => {
    const target = await loadWorkerTarget("PUSH-SEND-001");
    const body = { ...notification(), token: TOKEN };
    const response = await workerHandler(target, "PUSH-SEND-001").fetch(
      jsonRequest(`${WORKER_ORIGIN}/api/send/`, body, { headers: { Origin: SITE_ORIGIN, "Idempotency-Key": body.eventId } }),
      pushEnvironment(),
      new ExecutionContextRecorder(),
    );
    expect(response.status).toBe(401);
  });

  test("[PUSH-SEND-002] schema exige eventId, payloadHash, title, body y URL de nota", async () => {
    const target = await loadWorkerTarget("PUSH-SEND-002");
    const worker = workerHandler(target, "PUSH-SEND-002");
    for (const body of [{}, { ...notification(), eventId: undefined }, { ...notification(), payloadHash: undefined }, { ...notification(), payload: {} }]) {
      const response = await worker.fetch(sendRequest(body), pushEnvironment(), new ExecutionContextRecorder());
      expect(response.status).toBe(400);
    }
  });

  test("[PUSH-SEND-003] gate verifica que la URL desplegada responda 200 antes del fan-out", async () => {
    const target = await loadWorkerTarget("PUSH-SEND-003");
    const transport = new FetchRouter()
      .respond("HEAD", `${SITE_ORIGIN}/notas/ia-segura/`, new Response("", { status: 200 }));
    const response = await workerHandler(target, "PUSH-SEND-003").fetch(
      sendRequest(),
      pushEnvironment(new FakeKV(), { FETCH: transport.fetch }),
      new ExecutionContextRecorder(),
    );
    expect(response.status).toBe(200);
    expect(transport.calls[0]).toMatchObject({ method: "HEAD", url: `${SITE_ORIGIN}/notas/ia-segura/` });
  });

  test("[PUSH-SEND-004] gate 404/redirect/cross-origin aborta sin listar suscripciones", async () => {
    const target = await loadWorkerTarget("PUSH-SEND-004");
    for (const status of [301, 404, 500]) {
      const kv = new FakeKV();
      const transport = new FetchRouter().respond("HEAD", `${SITE_ORIGIN}/notas/ia-segura/`, new Response("", { status }));
      const response = await workerHandler(target, "PUSH-SEND-004").fetch(
        sendRequest(),
        pushEnvironment(kv, { FETCH: transport.fetch }),
        new ExecutionContextRecorder(),
      );
      expect(response.status).toBe(409);
      expect(kv.calls.filter((call) => call.operation === "list")).toHaveLength(0);
    }
  });

  test("[PUSH-SEND-005] Idempotency-Key y eventId deben coincidir exactamente", async () => {
    const target = await loadWorkerTarget("PUSH-SEND-005");
    const response = await workerHandler(target, "PUSH-SEND-005").fetch(
      sendRequest(notification(), { "Idempotency-Key": "other-event" }),
      pushEnvironment(),
      new ExecutionContextRecorder(),
    );
    expect(response.status).toBe(409);
  });

  test("[PUSH-SEND-006] cero suscriptores finaliza complete con resumen exacto", async () => {
    const target = await loadWorkerTarget("PUSH-SEND-006");
    const transport = new FetchRouter().respond("HEAD", `${SITE_ORIGIN}/notas/ia-segura/`, new Response("", { status: 200 }));
    const response = await workerHandler(target, "PUSH-SEND-006").fetch(
      sendRequest(),
      pushEnvironment(new FakeKV(), { FETCH: transport.fetch }),
      new ExecutionContextRecorder(),
    );
    expect(await response.json()).toEqual({
      eventId: notification().eventId,
      state: "complete",
      total: 0,
      delivered: 0,
      gone: 0,
      retryable: 0,
      uncertain: 0,
      invalid: 0,
      duplicate: false,
    });
  });

  test("[PUSH-SEND-007] un suscriptor recibe exactamente una entrega", async () => {
    const target = await loadWorkerTarget("PUSH-SEND-007");
    const kv = new FakeKV();
    await seedSubscriptions(kv, 1);
    const pushes = [];
    const response = await workerHandler(target, "PUSH-SEND-007").fetch(
      sendRequest(),
      pushEnvironment(kv, {
        FETCH: new FetchRouter().respond("HEAD", `${SITE_ORIGIN}/notas/ia-segura/`, new Response("", { status: 200 })).fetch,
        PUSH_TRANSPORT: async (sub, payload) => { pushes.push({ sub, payload }); return new Response("", { status: 201 }); },
      }),
      new ExecutionContextRecorder(),
    );
    expect(response.status).toBe(200);
    expect(pushes).toHaveLength(1);
    expect((await response.json()).delivered).toBe(1);
  });

  test("[PUSH-SEND-008] 50 suscriptores se procesan una vez en una página", async () => {
    const target = await loadWorkerTarget("PUSH-SEND-008");
    const kv = new FakeKV({ pageSize: 50 });
    await seedSubscriptions(kv, 50);
    const calls = [];
    await workerHandler(target, "PUSH-SEND-008").fetch(
      sendRequest(),
      pushEnvironment(kv, {
        FETCH: new FetchRouter().respond("HEAD", `${SITE_ORIGIN}/notas/ia-segura/`, new Response("", { status: 200 })).fetch,
        PUSH_TRANSPORT: async (sub) => { calls.push(sub.endpoint); return new Response("", { status: 201 }); },
      }),
      new ExecutionContextRecorder(),
    );
    expect(calls).toHaveLength(50);
    expect(new Set(calls).size).toBe(50);
  });

  test("[PUSH-SEND-009] 51 suscriptores atraviesan dos páginas sin omitir ni duplicar", async () => {
    const target = await loadWorkerTarget("PUSH-SEND-009");
    const kv = new FakeKV({ pageSize: 50 });
    await seedSubscriptions(kv, 51);
    const calls = [];
    await workerHandler(target, "PUSH-SEND-009").fetch(
      sendRequest(),
      pushEnvironment(kv, {
        FETCH: new FetchRouter().respond("HEAD", `${SITE_ORIGIN}/notas/ia-segura/`, new Response("", { status: 200 })).fetch,
        PUSH_TRANSPORT: async (sub) => { calls.push(sub.endpoint); return new Response("", { status: 201 }); },
      }),
      new ExecutionContextRecorder(),
    );
    expect(calls).toHaveLength(51);
    expect(new Set(calls).size).toBe(51);
    expect(kv.calls.filter((call) => call.operation === "list").length).toBeGreaterThanOrEqual(2);
  });

  test("[PUSH-SEND-010] re-run mismo evento y hash responde duplicate sin transporte", async () => {
    const target = await loadWorkerTarget("PUSH-SEND-010");
    const kv = new FakeKV();
    await seedSubscriptions(kv, 1);
    const pushes = [];
    const environment = pushEnvironment(kv, {
      FETCH: new FetchRouter().respond("HEAD", `${SITE_ORIGIN}/notas/ia-segura/`, new Response("", { status: 200 })).fetch,
      PUSH_TRANSPORT: async () => { pushes.push("push"); return new Response("", { status: 201 }); },
    });
    const worker = workerHandler(target, "PUSH-SEND-010");
    await worker.fetch(sendRequest(), environment, new ExecutionContextRecorder());
    const second = await worker.fetch(sendRequest(), environment, new ExecutionContextRecorder());
    expect((await second.json()).duplicate).toBe(true);
    expect(pushes).toHaveLength(1);
  });

  test("[PUSH-SEND-011] mismo eventId con payloadHash distinto devuelve 409 sin fan-out", async () => {
    const target = await loadWorkerTarget("PUSH-SEND-011");
    const kv = new FakeKV();
    const pushes = [];
    const environment = pushEnvironment(kv, {
      FETCH: new FetchRouter().respond("HEAD", `${SITE_ORIGIN}/notas/ia-segura/`, new Response("", { status: 200 })).fetch,
      PUSH_TRANSPORT: async () => { pushes.push("push"); return new Response("", { status: 201 }); },
    });
    const worker = workerHandler(target, "PUSH-SEND-011");
    await worker.fetch(sendRequest(), environment, new ExecutionContextRecorder());
    const changed = notification({ payloadHash: "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" });
    const response = await worker.fetch(sendRequest(changed), environment, new ExecutionContextRecorder());
    expect(response.status).toBe(409);
    expect(pushes.length).toBeLessThanOrEqual(1);
  });

  test("[PUSH-SEND-012] dos requests concurrentes del mismo evento ejecutan un único fan-out", async () => {
    const target = await loadWorkerTarget("PUSH-SEND-012");
    const kv = new FakeKV();
    await seedSubscriptions(kv, 1);
    const pushes = [];
    const environment = pushEnvironment(kv, {
      FETCH: new FetchRouter().respond("HEAD", `${SITE_ORIGIN}/notas/ia-segura/`, new Response("", { status: 200 })).fetch,
      PUSH_TRANSPORT: async () => { pushes.push("push"); return new Response("", { status: 201 }); },
    });
    const worker = workerHandler(target, "PUSH-SEND-012");
    const responses = await Promise.all([1, 2].map(() => worker.fetch(sendRequest(), environment, new ExecutionContextRecorder())));
    expect(pushes).toHaveLength(1);
    expect((await Promise.all(responses.map((response) => response.json()))).filter(({ duplicate }) => duplicate)).toHaveLength(1);
  });

  test("[PUSH-SEND-013] edición o deploy CSS no constituyen un nuevo evento de nota", async () => {
    const validate = await exported("validateNotificationEvent", "PUSH-SEND-013");
    expect(() => validate(notification({ eventId: "css:d2b6b8f" }))).toThrow(/event|blog-note/i);
    expect(() => validate(notification({ eventId: "blog-edit:2026-08-26:ia-segura" }))).toThrow(/event|new note/i);
    expect(validate(notification()).eventId).toBe(notification().eventId);
    const productionUnicodeEvent = "blog-note:2026-08-23:openai-pausa-su-entrenamiento-por-cibercapacidad-crítica-claude-diseña-proteínas-que-funcionan-y-qwen-corona-a-china-la-semana-en-que-la-ia-se-puso-frenos-a-sí-misma";
    expect(new TextEncoder().encode(productionUnicodeEvent).length).toBeGreaterThan(160);
    expect(validate(notification({ eventId: productionUnicodeEvent })).eventId).toBe(productionUnicodeEvent);
  });

  test("[PUSH-SEND-014] resumen cuenta delivered, gone, retryable, uncertain e invalid por separado", async () => {
    const summarize = await exported("summarizeDeliveries", "PUSH-SEND-014");
    expect(summarize(["delivered", "delivered", "gone", "retryable", "uncertain", "invalid"])).toEqual({
      total: 6,
      delivered: 2,
      gone: 1,
      retryable: 1,
      uncertain: 1,
      invalid: 1,
      state: "uncertain",
    });
  });

  test("[PUSH-SEND-015] 404/410 elimina suscripción; 429/5xx la conserva", async () => {
    const apply = await exported("applyDeliveryOutcome", "PUSH-SEND-015");
    for (const status of [404, 410]) {
      const kv = new FakeKV();
      await kv.put("sub:v1:a", "{}");
      await apply({ kv, subscriptionKey: "sub:v1:a", response: new Response("", { status }) });
      expect(await kv.get("sub:v1:a")).toBeNull();
    }
    for (const status of [429, 500, 503]) {
      const kv = new FakeKV();
      await kv.put("sub:v1:a", "{}");
      await apply({ kv, subscriptionKey: "sub:v1:a", response: new Response("", { status }) });
      expect(await kv.get("sub:v1:a")).toBe("{}");
    }
  });

  test("[PUSH-SEND-016] sólo retryable recibe una única reintento automático", async () => {
    const retry = await exported("retryDelivery", "PUSH-SEND-016");
    const transport = vi.fn(async () => new Response("", { status: 201 }));
    expect(await retry({ outcome: "retryable", attempt: 1, transport })).toMatchObject({ outcome: "delivered", attempt: 2 });
    expect(await retry({ outcome: "uncertain", attempt: 1, transport })).toMatchObject({ outcome: "uncertain", attempt: 1 });
    expect(await retry({ outcome: "retryable", attempt: 2, transport })).toMatchObject({ outcome: "retryable", attempt: 2 });
    expect(transport).toHaveBeenCalledTimes(1);
  });

  test("[PUSH-SEND-017] valor de suscripción corrupto se cuenta invalid y se elimina sin abortar lote", async () => {
    const target = await loadWorkerTarget("PUSH-SEND-017");
    const kv = new FakeKV();
    await kv.put("sub:v1:a", "not-json");
    await seedSubscriptions(kv, 1);
    const response = await workerHandler(target, "PUSH-SEND-017").fetch(
      sendRequest(),
      pushEnvironment(kv, {
        FETCH: new FetchRouter().respond("HEAD", `${SITE_ORIGIN}/notas/ia-segura/`, new Response("", { status: 200 })).fetch,
        PUSH_TRANSPORT: async () => new Response("", { status: 201 }),
      }),
      new ExecutionContextRecorder(),
    );
    expect(await response.json()).toMatchObject({ delivered: 1, invalid: 1 });
    expect(await kv.get("sub:v1:a")).toBeNull();
  });

  test("[PUSH-SEND-018] claves KV ajenas al prefijo sub se ignoran", async () => {
    const list = await exported("listSubscriptionsPaginated", "PUSH-SEND-018");
    const kv = new FakeKV();
    await kv.put("rate:v1:abc", "{}");
    await kv.put("delivery:v1:abc", "{}");
    await kv.put("sub:v1:abc", JSON.stringify({ schemaVersion: 1, subscription: validSubscription() }));
    const result = await list(kv, { pageSize: 50, maxTotal: 100 });
    expect(result.items).toHaveLength(1);
    expect(result.items[0].key).toBe("sub:v1:abc");
  });

  test("[PUSH-SEND-019] cursor cíclico se detecta y falla cerrado", async () => {
    const list = await exported("listSubscriptionsPaginated", "PUSH-SEND-019");
    const kv = { async list() { return { keys: [], list_complete: false, cursor: "same" }; } };
    await expect(list(kv, { pageSize: 50, maxTotal: 100 })).rejects.toThrow(/cursor|cycle/i);
  });

  test("[PUSH-SEND-020] límite total impide fan-out accidental ilimitado", async () => {
    const list = await exported("listSubscriptionsPaginated", "PUSH-SEND-020");
    const kv = new FakeKV({ pageSize: 50 });
    await seedSubscriptions(kv, 51);
    await expect(list(kv, { pageSize: 50, maxTotal: 50 })).rejects.toMatchObject({ status: 413 });
  });

  test("[PUSH-SEND-021] respuesta pública nunca incluye endpoint, provider body ni headers", async () => {
    const redact = await exported("redactForLog", "PUSH-SEND-021");
    const sensitive = {
      endpoint: "https://push.example.test/private",
      body: "provider secret body",
      headers: { Authorization: "secret" },
      status: 410,
      eventId: notification().eventId,
    };
    const result = JSON.stringify(redact(sensitive));
    expect(result).not.toMatch(/push\.example|provider secret|Authorization|secret/);
    expect(result).toContain("410");
  });

  test("[PUSH-SEND-022] ningún transporte comienza antes de auth, schema, deploy e idempotencia", async () => {
    const target = await loadWorkerTarget("PUSH-SEND-022");
    const calls = [];
    const environment = pushEnvironment(new FakeKV(), {
      FETCH: async () => { calls.push("gate"); return new Response("", { status: 404 }); },
      PUSH_TRANSPORT: async () => { calls.push("push"); return new Response("", { status: 201 }); },
    });
    const response = await workerHandler(target, "PUSH-SEND-022").fetch(sendRequest(), environment, new ExecutionContextRecorder());
    expect(response.status).toBe(409);
    expect(calls).toEqual(["gate"]);
  });
});

describe("Delivery classification, retention and redaction", () => {
  test("[PUSH-DELIVERY-001] classifyPushResponse clasifica 201/202 delivered", async () => {
    const classify = await exported("classifyPushResponse", "PUSH-DELIVERY-001");
    expect(classify(new Response("", { status: 201 }))).toBe("delivered");
    expect(classify(new Response("", { status: 202 }))).toBe("delivered");
  });

  test("[PUSH-DELIVERY-002] classifyPushResponse clasifica 404/410 gone", async () => {
    const classify = await exported("classifyPushResponse", "PUSH-DELIVERY-002");
    expect(classify(new Response("", { status: 404 }))).toBe("gone");
    expect(classify(new Response("", { status: 410 }))).toBe("gone");
  });

  test("[PUSH-DELIVERY-003] classifyPushResponse clasifica 408/425/429/5xx retryable", async () => {
    const classify = await exported("classifyPushResponse", "PUSH-DELIVERY-003");
    for (const status of [408, 425, 429, 500, 502, 503, 504, 599]) expect(classify(new Response("", { status }))).toBe("retryable");
  });

  test("[PUSH-DELIVERY-004] classifyPushResponse clasifica 400/401/403 invalid sin reintento", async () => {
    const classify = await exported("classifyPushResponse", "PUSH-DELIVERY-004");
    for (const status of [400, 401, 403]) expect(classify(new Response("", { status }))).toBe("invalid");
  });

  test("[PUSH-DELIVERY-005] timeout y error de red son uncertain, no retryable", async () => {
    const classify = await exported("classifyPushResponse", "PUSH-DELIVERY-005");
    expect(classify(new DOMException("timed out", "TimeoutError"))).toBe("uncertain");
    expect(classify(new TypeError("fetch failed"))).toBe("uncertain");
  });

  test("[PUSH-DELIVERY-006] recordDelivery persiste outcome, intento y timestamp con reloj fake", async () => {
    const record = await exported("recordDelivery", "PUSH-DELIVERY-006");
    const storage = new FakeDurableStorage();
    await record(storage, {
      eventId: notification().eventId,
      subscriptionKey: "sub:v1:a",
      outcome: "delivered",
      attempt: 1,
      now: FIXED_NOW,
    });
    const values = [...storage.data.values()];
    expect(values).toContainEqual(expect.objectContaining({ outcome: "delivered", attempt: 1, updatedAt: FIXED_NOW }));
  });

  test("[PUSH-DELIVERY-007] recordDelivery no persiste endpoint, payload ni provider body", async () => {
    const record = await exported("recordDelivery", "PUSH-DELIVERY-007");
    const storage = new FakeDurableStorage();
    await record(storage, {
      eventId: notification().eventId,
      subscriptionKey: "sub:v1:a",
      outcome: "gone",
      endpoint: "https://push.example.test/private",
      providerBody: "secret body",
      payload: notification().payload,
      now: FIXED_NOW,
    });
    expect(JSON.stringify([...storage.data.values()])).not.toMatch(/push\.example|secret body|Nueva nota/);
  });

  test("[PUSH-DELIVERY-008] purgeExpiredDeliveryRecords respeta antes, en y después del cutoff", async () => {
    const purge = await exported("purgeExpiredDeliveryRecords", "PUSH-DELIVERY-008");
    const storage = new FakeKV();
    await storage.put("delivery:before", JSON.stringify({ updatedAt: FIXED_NOW - 1 }));
    await storage.put("delivery:at", JSON.stringify({ updatedAt: FIXED_NOW }));
    await storage.put("delivery:after", JSON.stringify({ updatedAt: FIXED_NOW + 1 }));
    const result = await purge(storage, { cutoff: FIXED_NOW, batchSize: 50 });
    expect(result.deleted).toBe(1);
    expect(await storage.get("delivery:before")).toBeNull();
    expect(await storage.get("delivery:at")).not.toBeNull();
    expect(await storage.get("delivery:after")).not.toBeNull();
  });

  test("[PUSH-DELIVERY-009] purge usa batch/cursor y se reanuda luego de error parcial", async () => {
    const purge = await exported("purgeExpiredDeliveryRecords", "PUSH-DELIVERY-009");
    const storage = new FakeKV({ pageSize: 2 });
    for (let index = 0; index < 5; index += 1) await storage.put(`delivery:${index}`, JSON.stringify({ updatedAt: 0 }));
    storage.failNext("delete", new Error("transient"));
    await expect(purge(storage, { cutoff: 1, batchSize: 2 })).rejects.toMatchObject({ cursor: expect.anything() });
    const resumed = await purge(storage, { cutoff: 1, batchSize: 2 });
    expect(resumed.complete).toBe(true);
    expect(resumed.deleted).toBeGreaterThan(0);
  });

  test("[PUSH-DELIVERY-010] purge nunca borra subs, rate limits ni eventos activos", async () => {
    const purge = await exported("purgeExpiredDeliveryRecords", "PUSH-DELIVERY-010");
    const storage = new FakeKV();
    await storage.put("sub:v1:a", JSON.stringify({ updatedAt: 0 }));
    await storage.put("rate:v1:a", JSON.stringify({ updatedAt: 0 }));
    await storage.put("notification:v1:active", JSON.stringify({ state: "pending", updatedAt: 0 }));
    await purge(storage, { cutoff: 1, batchSize: 50 });
    expect(await storage.get("sub:v1:a")).not.toBeNull();
    expect(await storage.get("rate:v1:a")).not.toBeNull();
    expect(await storage.get("notification:v1:active")).not.toBeNull();
  });

  test("[PUSH-DELIVERY-011] finalizeNotification es idempotente y no altera timestamps al repetir", async () => {
    const finalize = await exported("finalizeNotification", "PUSH-DELIVERY-011");
    const storage = new FakeDurableStorage();
    const input = { eventId: notification().eventId, expectedDeliveries: 0, now: FIXED_NOW };
    const first = await finalize(storage, input);
    const second = await finalize(storage, { ...input, now: FIXED_NOW + 60_000 });
    expect(second).toEqual(first);
    expect(second.updatedAt).toBe(FIXED_NOW);
  });

  test("[PUSH-DELIVERY-012] redactForLog maneja ciclos, Error y headers sin arrojar", async () => {
    const redact = await exported("redactForLog", "PUSH-DELIVERY-012");
    const cyclic = { endpoint: "https://push.example/private", error: new Error("secret token") };
    cyclic.self = cyclic;
    expect(() => JSON.stringify(redact(cyclic))).not.toThrow();
    expect(JSON.stringify(redact(cyclic))).not.toMatch(/push\.example|secret token|stack/i);
  });
});

describe("KV, pagination and concurrency helpers", () => {
  test("[PUSH-KV-001] FakeKV implementa put/get/delete y clona metadata", async () => {
    const kv = new FakeKV();
    const metadata = { schemaVersion: 1 };
    await kv.put("sub:a", "value", { metadata });
    metadata.schemaVersion = 2;
    expect(await kv.get("sub:a")).toBe("value");
    expect((await kv.getWithMetadata("sub:a")).metadata).toEqual({ schemaVersion: 1 });
    await kv.delete("sub:a");
    expect(await kv.get("sub:a")).toBeNull();
  });

  test("[PUSH-KV-002] FakeKV aplica expirationTtl con reloj determinista", async () => {
    const clock = new FakeClock();
    const kv = new FakeKV({ clock });
    await kv.put("sub:a", "value", { expirationTtl: 60 });
    clock.advance(59_999);
    expect(await kv.get("sub:a")).toBe("value");
    clock.advance(1);
    expect(await kv.get("sub:a")).toBeNull();
  });

  test("[PUSH-KV-003] FakeKV pagina en orden determinista y filtra prefijo", async () => {
    const kv = new FakeKV({ pageSize: 2 });
    for (const key of ["sub:c", "other:a", "sub:a", "sub:b"]) await kv.put(key, key);
    const first = await kv.list({ prefix: "sub:", limit: 50 });
    const second = await kv.list({ prefix: "sub:", limit: 50, cursor: first.cursor });
    expect(first.keys.map(({ name }) => name)).toEqual(["sub:a", "sub:b"]);
    expect(second.keys.map(({ name }) => name)).toEqual(["sub:c"]);
    expect(second.list_complete).toBe(true);
  });

  test("[PUSH-KV-004] claves notification, delivery, rate y sub tienen versión y encoding acotado", async () => {
    const target = await loadWorkerTarget("PUSH-KV-004");
    for (const [name, args] of [
      ["subscriptionKey", ["https://push.example.test/á"]],
      ["notificationKey", ["blog-note:á", "sha256:abc"]],
      ["deliveryKey", ["blog-note:á", "sub:v1:abc"]],
    ]) {
      const fn = requireFunction(target, name, "PUSH-KV-004");
      const key = await fn(...args);
      expect(key).toMatch(/:v\d+:/);
      expect(new TextEncoder().encode(key).length).toBeLessThanOrEqual(512);
      expect(key).not.toContain("á");
    }
  });

  test("[PUSH-KV-005] listSubscriptionsPaginated tolera valor ausente y reporta corrupto", async () => {
    const list = await exported("listSubscriptionsPaginated", "PUSH-KV-005");
    const kv = new FakeKV();
    await kv.put("sub:v1:missing", "{}");
    await kv.put("sub:v1:corrupt", "not-json");
    await kv.put("sub:v1:valid", JSON.stringify({ schemaVersion: 1, subscription: validSubscription() }));
    const originalGet = kv.get.bind(kv);
    kv.get = async (key, options) => key === "sub:v1:missing" ? null : originalGet(key, options);
    const result = await list(kv, { pageSize: 50, maxTotal: 100 });
    expect(result.items).toHaveLength(1);
    expect(result.invalid.sort()).toEqual(["sub:v1:corrupt", "sub:v1:missing"]);
  });

  test("[PUSH-KV-006] limitedConcurrency procesa 0, 1 y N elementos conservando orden", async () => {
    const limited = await exported("limitedConcurrency", "PUSH-KV-006");
    expect(await limited([], 3, async (value) => value)).toEqual([]);
    expect(await limited([1], 3, async (value) => value * 2)).toEqual([2]);
    expect(await limited([1, 2, 3, 4], 2, async (value) => value * 2)).toEqual([2, 4, 6, 8]);
  });

  test("[PUSH-KV-007] limitedConcurrency respeta el máximo y ejecuta cada item una vez", async () => {
    const limited = await exported("limitedConcurrency", "PUSH-KV-007");
    let active = 0;
    let maximum = 0;
    const seen = [];
    const gates = [];
    const resultPromise = limited([0, 1, 2, 3, 4, 5], 2, async (value) => {
      active += 1;
      maximum = Math.max(maximum, active);
      seen.push(value);
      await new Promise((resolve) => gates.push(resolve));
      active -= 1;
      return value;
    });
    await Promise.resolve();
    expect(maximum).toBe(2);
    while (gates.length) {
      gates.shift()();
      await Promise.resolve();
    }
    await resultPromise;
    expect(maximum).toBe(2);
    expect(seen.sort((a, b) => a - b)).toEqual([0, 1, 2, 3, 4, 5]);
  });

  test("[PUSH-KV-008] limitedConcurrency rechaza límite cero/negativo y propaga callback sin flotantes", async () => {
    const limited = await exported("limitedConcurrency", "PUSH-KV-008");
    await expect(limited([1], 0, async (value) => value)).rejects.toThrow(/concurrency|positive/i);
    await expect(limited([1], -1, async (value) => value)).rejects.toThrow(/concurrency|positive/i);
    await expect(limited([1, 2], 1, async (value) => { if (value === 2) throw new Error("callback failed"); return value; }))
      .rejects.toThrow("callback failed");
  });

  test("[PUSH-KV-009] FetchRouter y ExecutionContextRecorder no permiten red ni promesas ocultas", async () => {
    const router = new FetchRouter().respond("GET", "https://fixture.test/value", new Response("ok", { status: 200 }));
    expect(await (await router.fetch("https://fixture.test/value")).text()).toBe("ok");
    await expect(router.fetch("https://unconfigured.test/value")).rejects.toThrow(/JS-NET-ROUTER-001/);
    const ctx = new ExecutionContextRecorder();
    ctx.waitUntil(Promise.resolve("done"));
    ctx.waitUntil(Promise.reject(new Error("captured")));
    expect((await ctx.drain()).map(({ status }) => status)).toEqual(["fulfilled", "rejected"]);
  });

  test("[PUSH-KV-010] API productiva no expone clear-all ni listado global de claves", async () => {
    const target = await loadWorkerTarget("PUSH-KV-010");
    const worker = workerHandler(target, "PUSH-KV-010");
    for (const [method, path] of [["POST", "/api/debug/clear-all"], ["GET", "/api/subscriptions"], ["GET", "/api/keys"]]) {
      const response = await worker.fetch(new Request(`${WORKER_ORIGIN}${path}`, { method, headers: { Authorization: `Bearer ${TOKEN}` }, body: method === "GET" ? undefined : "{}" }), pushEnvironment(), new ExecutionContextRecorder());
      expect(response.status).toBe(404);
    }
  });
});
