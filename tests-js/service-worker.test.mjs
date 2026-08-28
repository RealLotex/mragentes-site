import { describe, expect, test as vitestTest } from "vitest";

import { createServiceWorkerHarness } from "./support/fake-sw.mjs";
import { tracedTest } from "./support/trace-test.mjs";

const test = tracedTest(vitestTest);
const ORIGIN = "https://mragentes.com.ar";

describe("static/sw.js install, activate and fetch", () => {
  test("[PUSH-SW-001] install llama skipWaiting y captura precache completo en waitUntil", async () => {
    const harness = await createServiceWorkerHarness();
    const event = harness.event();
    const result = await harness.dispatch("install", event);
    expect(result.handled).toBe(true);
    expect(harness.calls.skipWaiting).toBe(1);
    expect(event.waited).toHaveLength(1);
    expect((await event.drain()).every(({ status }) => status === "fulfilled")).toBe(true);
    expect(await harness.caches.keys()).toHaveLength(1);
  });

  test("[PUSH-SW-002] precache estable tolera opcionales pero conserva shell esencial visible", async () => {
    const harness = await createServiceWorkerHarness({
      fetchImpl: async (input) => {
        const pathname = new URL(input, ORIGIN).pathname;
        if (pathname.includes("alegreya")) return new Response("missing", { status: 404 });
        return new Response(pathname, { status: 200 });
      },
    });
    const event = harness.event();
    await harness.dispatch("install", event);
    const settled = await event.drain();
    expect(settled.every(({ status }) => status === "fulfilled")).toBe(true);
    const [cacheName] = await harness.caches.keys();
    const cache = await harness.caches.open(cacheName);
    expect(await cache.match(`${ORIGIN}/`)).toBeDefined();
    expect(await cache.match(`${ORIGIN}/notas/`)).toBeDefined();
    expect(await cache.match(`${ORIGIN}/faviconhand512.png`)).toBeDefined();
    expect(await cache.match(`${ORIGIN}/fonts/alegreya-normal-latin.woff2`)).toBeUndefined();
  });

  test("[PUSH-SW-003] activate borra sólo caches MR Agentes obsoletos y reclama clientes", async () => {
    const harness = await createServiceWorkerHarness();
    await harness.caches.open("mragentes-v5");
    await harness.caches.open("mragentes-v6");
    await harness.caches.open("other-app-v1");
    const event = harness.event();
    await harness.dispatch("activate", event);
    await event.drain();
    expect(harness.caches.deleted).toContain("mragentes-v5");
    expect(harness.caches.deleted).not.toContain("mragentes-v6");
    expect(harness.caches.deleted).not.toContain("other-app-v1");
    expect(harness.calls.claim).toBe(1);
  });

  test("[PUSH-SW-004] fetch ignora no-GET, cross-origin y recursos no estáticos", async () => {
    const harness = await createServiceWorkerHarness();
    for (const request of [
      new Request(`${ORIGIN}/assets/app.js`, { method: "POST", body: "x" }),
      new Request("https://cdn.example.test/assets/app.js"),
      new Request(`${ORIGIN}/notas/una-nota/`),
      new Request(`${ORIGIN}/api/value.json`),
    ]) {
      const event = harness.fetchEvent(request);
      await harness.dispatch("fetch", event);
      expect(event.response(), `${request.method} ${request.url}`).toBeUndefined();
    }
    expect(harness.calls.fetch).toHaveLength(0);
  });

  test("[PUSH-SW-005] fetch usa cache hit, guarda sólo 200 y captura cache.put en waitUntil", async () => {
    const harness = await createServiceWorkerHarness({
      fetchImpl: async (input) => new Response(`network:${new URL(input).pathname}`, { status: 200 }),
    });
    const cache = await harness.caches.open("mragentes-v6");
    await cache.put(`${ORIGIN}/assets/hit.js`, new Response("cached", { status: 200 }));

    const hit = harness.fetchEvent(new Request(`${ORIGIN}/assets/hit.js`));
    await harness.dispatch("fetch", hit);
    expect(await (await hit.response()).text()).toBe("cached");
    expect(harness.calls.fetch).toHaveLength(0);

    const miss = harness.fetchEvent(new Request(`${ORIGIN}/assets/miss.js`));
    await harness.dispatch("fetch", miss);
    expect(await (await miss.response()).text()).toBe("network:/assets/miss.js");
    expect(miss.waited).toHaveLength(1);
    await miss.drain();
    expect(await cache.match(`${ORIGIN}/assets/miss.js`)).toBeDefined();
  });

  test("[PUSH-SW-006] fetch offline entrega hit existente y rechaza miss sin cachear error", async () => {
    const harness = await createServiceWorkerHarness({ fetchImpl: async () => { throw new TypeError("offline"); } });
    const cache = await harness.caches.open("mragentes-v6");
    await cache.put(`${ORIGIN}/assets/offline.css`, new Response("cached css", { status: 200 }));
    const hit = harness.fetchEvent(new Request(`${ORIGIN}/assets/offline.css`));
    await harness.dispatch("fetch", hit);
    expect(await (await hit.response()).text()).toBe("cached css");

    const miss = harness.fetchEvent(new Request(`${ORIGIN}/assets/missing.css`));
    await harness.dispatch("fetch", miss);
    await expect(miss.response()).rejects.toThrow("offline");
    expect(await cache.match(`${ORIGIN}/assets/missing.css`)).toBeUndefined();
  });
});

describe("static/sw.js push and notification interactions", () => {
  test("[PUSH-SW-007] push JSON válido muestra branding, tag, image y URL same-origin", async () => {
    const harness = await createServiceWorkerHarness();
    const event = harness.pushEvent({
      title: "Nota nueva",
      body: "Resumen",
      url: `${ORIGIN}/notas/nota-nueva/`,
      icon: "/faviconhand512.png",
      badge: "/faviconhand512.png",
      image: `${ORIGIN}/images/stock/nota.webp`,
      tag: "blog-note:nota-nueva",
    });
    await harness.dispatch("push", event);
    expect(event.waited).toHaveLength(1);
    await event.drain();
    expect(harness.calls.showNotification).toEqual([{
      title: "Nota nueva",
      options: expect.objectContaining({
        body: "Resumen",
        icon: "/faviconhand512.png",
        badge: "/faviconhand512.png",
        image: `${ORIGIN}/images/stock/nota.webp`,
        tag: "blog-note:nota-nueva",
        data: expect.objectContaining({ url: `${ORIGIN}/notas/nota-nueva/` }),
      }),
    }]);
  });

  test("[PUSH-SW-008] push ausente o JSON inválido usa defaults de marca y siempre espera showNotification", async () => {
    for (const data of [undefined, new Error("invalid json")]) {
      const harness = await createServiceWorkerHarness();
      const event = harness.pushEvent(data);
      await harness.dispatch("push", event);
      expect(event.waited).toHaveLength(1);
      expect((await event.drain())[0].status).toBe("fulfilled");
      expect(harness.calls.showNotification[0]).toMatchObject({
        title: expect.stringMatching(/MR Agentes/),
        options: {
          body: expect.any(String),
          icon: "/faviconhand512.png",
          badge: "/faviconhand512.png",
          data: expect.objectContaining({ url: "/" }),
          actions: expect.any(Array),
          tag: expect.any(String),
          vibrate: expect.any(Array),
          renotify: expect.any(Boolean),
          requireInteraction: expect.any(Boolean),
        },
      });
    }
  });

  test("[PUSH-SW-009] push bloquea URL e imagen externas, javascript, data y traversal", async () => {
    for (const payload of [
      { url: "https://evil.test/phish", image: "https://evil.test/image.png" },
      { url: "javascript:alert(1)", image: "data:image/png;base64,AAAA" },
      { url: "/notas/%2e%2e/admin/", image: "/images/stock/%2e%2e/private.png" },
    ]) {
      const harness = await createServiceWorkerHarness();
      const event = harness.pushEvent({ title: "T", ...payload });
      await harness.dispatch("push", event);
      await event.drain();
      const options = harness.calls.showNotification[0].options;
      expect(options.data.url).toBe("/");
      expect(options).not.toHaveProperty("image");
    }
  });

  test("[PUSH-SW-010] notificationclick normaliza URL y enfoca cliente existente same-origin", async () => {
    const focused = [];
    const clients = [{
      url: `${ORIGIN}/notas/nota-nueva/`,
      async focus() { focused.push(this.url); return this; },
    }];
    const harness = await createServiceWorkerHarness({ clients });
    const closeCalls = [];
    const event = harness.event({
      action: "open",
      notification: {
        data: { url: "/notas/nota-nueva/" },
        close() { closeCalls.push("close"); },
      },
    });
    await harness.dispatch("notificationclick", event);
    await event.drain();
    expect(closeCalls).toEqual(["close"]);
    expect(focused).toEqual([`${ORIGIN}/notas/nota-nueva/`]);
    expect(harness.calls.openWindow).toHaveLength(0);
  });

  test("[PUSH-SW-011] click abre same-origin, bloquea externo y acción desconocida no navega", async () => {
    const cases = [
      { action: "open", url: "/notas/nueva/", expected: `${ORIGIN}/notas/nueva/` },
      { action: "open", url: "https://evil.test/phish", expected: `${ORIGIN}/` },
      { action: "delete-everything", url: "/notas/nueva/", expected: null },
    ];
    for (const { action, url, expected } of cases) {
      const harness = await createServiceWorkerHarness();
      const event = harness.event({
        action,
        notification: { data: { url }, close() {} },
      });
      await harness.dispatch("notificationclick", event);
      await event.drain();
      expect(harness.calls.openWindow, `${action} ${url}`).toEqual(expected ? [expected] : []);
    }
  });

  test("[PUSH-SW-012] message sólo acepta tipo/origin/payload allowlisted y usa waitUntil", async () => {
    const harness = await createServiceWorkerHarness();
    const cases = [
      { origin: "https://evil.test", data: { type: "SHOW_NOTIFICATION", payload: { title: "evil" } }, allowed: false },
      { origin: ORIGIN, data: { type: "UNKNOWN", payload: { title: "unknown" } }, allowed: false },
      { origin: ORIGIN, data: { type: "SHOW_NOTIFICATION", payload: { title: "Local", url: "/notas/local/" } }, allowed: true },
    ];
    for (const item of cases) {
      const before = harness.calls.showNotification.length;
      const event = harness.event({ origin: item.origin, data: item.data });
      await harness.dispatch("message", event);
      await event.drain();
      expect(harness.calls.showNotification.length - before).toBe(item.allowed ? 1 : 0);
      expect(event.waited.length).toBe(item.allowed ? 1 : 0);
    }
  });

  test("[PUSH-SW-013] pushsubscriptionchange renueva con VAPID, registra backend y deja retry durable ante fallo", async () => {
    const harness = await createServiceWorkerHarness();
    const subscriptions = [];
    harness.registration.pushManager.subscribe = async (options) => {
      subscriptions.push(options);
      return {
        endpoint: "https://push.example.test/renewed",
        toJSON() { return { endpoint: this.endpoint, keys: { p256dh: "key", auth: "auth" } }; },
      };
    };
    const event = harness.event({
      oldSubscription: { options: { applicationServerKey: new Uint8Array([1, 2, 3]) } },
    });
    const result = await harness.dispatch("pushsubscriptionchange", event);
    expect(result.handled).toBe(true);
    expect(event.waited).toHaveLength(1);
    await event.drain();
    expect(subscriptions).toHaveLength(1);
    expect(subscriptions[0]).toMatchObject({ userVisibleOnly: true });
    const registrationCall = harness.calls.fetch.find(
      ({ input }) => new URL(String(input)).pathname === "/api/subscribe/",
    );
    expect(registrationCall).toBeDefined();
    expect(new URL(String(registrationCall.input)).origin).toBe(
      "https://mragentes-push.rosichmarcos.workers.dev",
    );
    expect(new URL(String(registrationCall.input)).origin).not.toBe(ORIGIN);
    expect(harness.calls.showNotification).toHaveLength(0);
  });

  test("[PUSH-SW-014] se retira polling index: no NOTA_LIST_URL, checkForNewContent ni NEW_NOTA", async () => {
    const harness = await createServiceWorkerHarness();
    expect(harness.source).not.toMatch(/NOTA_LIST_URL/);
    expect(harness.source).not.toMatch(/checkForNewContent/);
    expect(harness.source).not.toMatch(/static\/notas\/index\.json|\/notas\/index\.json/);
    expect(harness.source).not.toMatch(/NEW_NOTA/);
  });
});
