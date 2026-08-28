import { describe, expect, test as vitestTest } from "vitest";

import { createPushClientHarness, makeSubscription } from "./support/fake-dom.mjs";
import { tracedTest } from "./support/trace-test.mjs";

const test = tracedTest(vitestTest);
const VALID_VAPID = "BAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";

function vapidBytes(value = VALID_VAPID) {
  return Uint8Array.from(Buffer.from(value, "base64url"));
}

async function loadingHarness(options = {}) {
  return createPushClientHarness({ readyState: "loading", ...options });
}

describe("assets/js/push.js public helpers and initialization", () => {
  test("[PUSH-CLIENT-001] meta distingue ausente y normaliza vacío, whitespace y valor", async () => {
    const harness = await loadingHarness();
    try {
      expect(harness.api.meta("push-api-url")).toBe("https://push.mragentes.test");
      expect(harness.api.meta("missing")).toBe("");
      const meta = harness.document.querySelector('meta[name="push-api-url"]');
      meta.content = "   ";
      expect(harness.api.meta("push-api-url")).toBe("");
      meta.content = " https://push.mragentes.test/path ";
      expect(harness.api.meta("push-api-url")).toBe("https://push.mragentes.test/path");
    } finally {
      harness.close();
    }
  });

  test("[PUSH-CLIENT-002] b64ToBytes soporta base64url, padding, vacío, binario y rechaza inválido", async () => {
    const harness = await loadingHarness();
    try {
      expect(harness.api.b64ToBytes("")).toEqual(new harness.window.Uint8Array());
      expect([...harness.api.b64ToBytes("AQI")]).toEqual([1, 2]);
      expect([...harness.api.b64ToBytes("AQI=")]).toEqual([1, 2]);
      expect([...harness.api.b64ToBytes("-_8")]).toEqual([251, 255]);
      for (const invalid of ["%", "A", "A A", "á", "AQ==="]) {
        expect(() => harness.api.b64ToBytes(invalid), invalid).toThrow(/base64|invalid|character|length/i);
      }
    } finally {
      harness.close();
    }
  });

  test("[PUSH-CLIENT-003] iosNeedsInstall cubre iPhone, iPadOS desktop, standalone y matchMedia ausente", async () => {
    const iphone = await loadingHarness({ userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0)", standalone: false });
    const ipadDesktop = await loadingHarness({ userAgent: "Mozilla/5.0", platform: "MacIntel", maxTouchPoints: 5, standalone: false });
    const installed = await loadingHarness({ userAgent: "Mozilla/5.0 (iPhone)", standalone: true });
    const noMatchMedia = await loadingHarness({ userAgent: "Mozilla/5.0 (iPhone)", standalone: false });
    try {
      expect(iphone.api.iosNeedsInstall()).toBe(true);
      expect(ipadDesktop.api.iosNeedsInstall()).toBe(true);
      expect(installed.api.iosNeedsInstall()).toBe(false);
      delete noMatchMedia.window.matchMedia;
      expect(() => noMatchMedia.api.iosNeedsInstall()).not.toThrow();
      expect(noMatchMedia.api.iosNeedsInstall()).toBe(true);
    } finally {
      iphone.close();
      ipadDesktop.close();
      installed.close();
      noMatchMedia.close();
    }
  });

  test("[PUSH-CLIENT-004] supported evalúa todas las combinaciones sin acceder globals ausentes", async () => {
    const harness = await loadingHarness();
    try {
      expect(harness.api.supported()).toBe(true);
      delete harness.window.PushManager;
      expect(harness.api.supported()).toBe(false);
      harness.window.PushManager = class PushManager {};
      delete harness.window.Notification;
      expect(() => harness.api.supported()).not.toThrow();
      expect(harness.api.supported()).toBe(false);
      harness.window.Notification = class Notification {};
      delete harness.window.navigator.serviceWorker;
      expect(harness.api.supported()).toBe(false);
    } finally {
      harness.close();
    }
  });

  test("[PUSH-CLIENT-005] keyMatches exige claves presentes, verificables y byte a byte iguales", async () => {
    const harness = await loadingHarness();
    try {
      expect(harness.api.keyMatches(makeSubscription({ applicationServerKey: vapidBytes() }))).toBe(true);
      expect(harness.api.keyMatches(makeSubscription({ applicationServerKey: new Uint8Array(vapidBytes().length) }))).toBe(false);
      expect(harness.api.keyMatches(makeSubscription({ applicationServerKey: new Uint8Array([1, 2]) }))).toBe(false);
      expect(harness.api.keyMatches(makeSubscription())).toBe(false);
      const noVapid = await loadingHarness({ vapid: "" });
      try {
        expect(noVapid.api.keyMatches(makeSubscription({ applicationServerKey: vapidBytes() }))).toBe(false);
      } finally {
        noVapid.close();
      }
    } finally {
      harness.close();
    }
  });

  test("[PUSH-CLIENT-006] init tolera DOM parcial y bloquea configuración API/VAPID ausente", async () => {
    const noButton = await loadingHarness({ withButton: false });
    const noStatus = await loadingHarness({ withStatus: false });
    const noApi = await loadingHarness({ api: "" });
    const noVapid = await loadingHarness({ vapid: "" });
    try {
      expect(() => noButton.dispatchReady()).not.toThrow();
      noStatus.dispatchReady();
      noApi.dispatchReady();
      noVapid.dispatchReady();
      await Promise.all([noStatus.flush(), noApi.flush(), noVapid.flush()]);
      expect(noApi.button.hidden).toBe(true);
      expect(noApi.status.textContent).toMatch(/configuraci[oó]n|no disponible/i);
      expect(noVapid.button.hidden).toBe(true);
      expect(noVapid.status.textContent).toMatch(/configuraci[oó]n|no disponible/i);
    } finally {
      noButton.close();
      noStatus.close();
      noApi.close();
      noVapid.close();
    }
  });

  test("[PUSH-CLIENT-007] unsupported y permiso denied ocultan botón con feedback accesible", async () => {
    const unsupported = await loadingHarness();
    delete unsupported.window.PushManager;
    const denied = await loadingHarness({ notificationPermission: "denied" });
    try {
      unsupported.dispatchReady();
      denied.dispatchReady();
      await Promise.all([unsupported.flush(), denied.flush()]);
      expect(unsupported.button.hidden).toBe(true);
      expect(unsupported.status.textContent).toMatch(/no admite|pantalla de inicio|RSS/i);
      expect(denied.button.hidden).toBe(true);
      expect(denied.status.textContent).toMatch(/bloquead|configuraci[oó]n/i);
      expect(unsupported.status.getAttribute("aria-live")).toBe("polite");
    } finally {
      unsupported.close();
      denied.close();
    }
  });

  test("[PUSH-CLIENT-008] init no anuncia activo hasta confirmación remota de la suscripción", async () => {
    let release;
    const pending = new Promise((resolve) => { release = resolve; });
    const sub = makeSubscription({ applicationServerKey: vapidBytes() });
    const harness = await loadingHarness({
      subscription: sub,
      fetchImpl: async () => pending,
    });
    try {
      harness.dispatchReady();
      await harness.flush();
      expect(harness.status.textContent).toMatch(/verificando|comprobando|sincronizando/i);
      expect(harness.button.getAttribute("aria-pressed")).not.toBe("true");
      release(new Response("", { status: 200 }));
      await harness.flush();
      expect(harness.status.textContent).toMatch(/Activado/);
      expect(harness.button.getAttribute("aria-pressed")).toBe("true");
    } finally {
      harness.close();
    }
  });

  test("[PUSH-CLIENT-009] init se ejecuta exactamente una vez aunque DOMContentLoaded se observe dos veces", async () => {
    const harness = await loadingHarness();
    try {
      harness.dispatchReady();
      harness.dispatchReady();
      await harness.flush();
      expect(harness.calls.register).toHaveLength(1);
      harness.button.click();
      await harness.flush();
      expect(harness.calls.subscribe).toHaveLength(1);
    } finally {
      harness.close();
    }
  });

  test("[PUSH-CLIENT-010] render ofrece labels on/off/loading/error, aria-pressed y foco estable", async () => {
    const harness = await loadingHarness({ fetchImpl: async () => new Response("", { status: 201 }) });
    try {
      harness.dispatchReady();
      await harness.flush();
      expect(harness.button.textContent).toMatch(/Avisarme/);
      expect(harness.button.getAttribute("aria-pressed")).toBe("false");
      harness.button.focus();
      harness.button.click();
      expect(harness.button.disabled).toBe(true);
      expect(harness.status.textContent).toMatch(/activando|procesando|esper/i);
      await harness.flush();
      expect(harness.button.textContent).toMatch(/Desactivar/);
      expect(harness.button.getAttribute("aria-pressed")).toBe("true");
      expect(harness.document.activeElement).toBe(harness.button);
      expect(harness.status.getAttribute("aria-live")).toBe("polite");
    } finally {
      harness.close();
    }
  });
});

describe("assets/js/push.js subscribe, revalidation and drop", () => {
  test("[PUSH-CLIENT-011] revalidate diferencia sin sub y clave igual sin recrearla", async () => {
    const off = await loadingHarness();
    const existing = makeSubscription({ applicationServerKey: vapidBytes() });
    const on = await loadingHarness({ subscription: existing, fetchImpl: async () => new Response("", { status: 200 }) });
    try {
      off.dispatchReady();
      on.dispatchReady();
      await Promise.all([off.flush(), on.flush()]);
      expect(off.button.getAttribute("aria-pressed")).toBe("false");
      expect(off.calls.subscribe).toHaveLength(0);
      expect(on.button.getAttribute("aria-pressed")).toBe("true");
      expect(on.calls.unsubscribe).toHaveLength(0);
      expect(on.calls.subscribe).toHaveLength(0);
    } finally {
      off.close();
      on.close();
    }
  });

  test("[PUSH-CLIENT-012] clave VAPID rotada espera drop remoto completo antes de add", async () => {
    const order = [];
    let releaseDrop;
    const dropResponse = new Promise((resolve) => { releaseDrop = resolve; });
    const old = makeSubscription({
      applicationServerKey: new Uint8Array(vapidBytes().length),
      calls: { unsubscribe: [] },
      onUnsubscribe: () => order.push("local-unsubscribe"),
    });
    const harness = await loadingHarness({
      subscription: old,
      fetchImpl: async (input) => {
        const path = new URL(input).pathname;
        order.push(path);
        if (path.endsWith("/unsubscribe/")) return dropResponse;
        return new Response("", { status: 201 });
      },
    });
    try {
      const originalSubscribe = harness.registration.pushManager.subscribe;
      harness.registration.pushManager.subscribe = async (options) => {
        order.push("subscribe");
        return originalSubscribe(options);
      };
      harness.dispatchReady();
      await harness.flush();
      expect(order).toEqual(["/api/unsubscribe/"]);
      releaseDrop(new Response("", { status: 200 }));
      await harness.flush(16);
      expect(order).toEqual(["/api/unsubscribe/", "local-unsubscribe", "subscribe", "/api/subscribe/"]);
    } finally {
      harness.close();
    }
  });

  test("[PUSH-CLIENT-013] KV perdido re-registra silenciosamente y no solicita bienvenida", async () => {
    const existing = makeSubscription({ applicationServerKey: vapidBytes() });
    const harness = await loadingHarness({
      subscription: existing,
      fetchImpl: async (input, init) => {
        const body = JSON.parse(init.body);
        expect(body.revalidate).toBe(true);
        return new Response(JSON.stringify({ created: true, revalidated: true, welcomeScheduled: false }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      },
    });
    try {
      harness.dispatchReady();
      await harness.flush();
      expect(harness.calls.fetch).toHaveLength(1);
      expect(new URL(harness.calls.fetch[0].input).pathname).toBe("/api/subscribe/");
      expect(harness.calls.unsubscribe).toHaveLength(0);
      expect(harness.calls.subscribe).toHaveLength(0);
      expect(harness.status.textContent).toMatch(/Activado/);
    } finally {
      harness.close();
    }
  });

  test("[PUSH-CLIENT-014] add pide permiso y subscribe usa userVisibleOnly más VAPID exacta", async () => {
    const harness = await loadingHarness({
      notificationPermission: "default",
      requestPermissionResult: "granted",
      fetchImpl: async () => new Response("", { status: 201 }),
    });
    try {
      harness.dispatchReady();
      await harness.flush();
      harness.button.click();
      await harness.flush();
      expect(harness.calls.permission).toHaveLength(1);
      expect(harness.calls.subscribe).toHaveLength(1);
      expect(harness.calls.subscribe[0].userVisibleOnly).toBe(true);
      expect(new Uint8Array(harness.calls.subscribe[0].applicationServerKey)).toEqual(vapidBytes());
      expect(harness.button.getAttribute("aria-pressed")).toBe("true");
    } finally {
      harness.close();
    }
  });

  test("[PUSH-CLIENT-015] rechazo, timeout o red del POST hacen rollback local y feedback de error", async () => {
    for (const failure of [
      async () => new Response("rejected", { status: 500 }),
      async () => { throw new DOMException("timeout", "TimeoutError"); },
      async () => { throw new TypeError("network down"); },
    ]) {
      const harness = await loadingHarness({ fetchImpl: failure });
      try {
        harness.dispatchReady();
        await harness.flush();
        harness.button.click();
        await harness.flush(16);
        expect(harness.calls.unsubscribe).toHaveLength(1);
        expect(harness.button.getAttribute("aria-pressed")).toBe("false");
        expect(harness.status.textContent).toMatch(/No se pudo|error/i);
        expect(harness.button.disabled).toBe(false);
      } finally {
        harness.close();
      }
    }
  });

  test("[PUSH-CLIENT-016] doble click sólo inicia una operación y finally siempre rehabilita botón", async () => {
    let release;
    const response = new Promise((resolve) => { release = resolve; });
    const harness = await loadingHarness({ fetchImpl: async () => response });
    try {
      harness.dispatchReady();
      await harness.flush();
      harness.button.dispatchEvent(new harness.window.MouseEvent("click", { bubbles: true }));
      harness.button.dispatchEvent(new harness.window.MouseEvent("click", { bubbles: true }));
      await harness.flush();
      expect(harness.calls.subscribe).toHaveLength(1);
      expect(harness.calls.fetch).toHaveLength(1);
      expect(harness.button.disabled).toBe(true);
      release(new Response("", { status: 201 }));
      await harness.flush(16);
      expect(harness.button.disabled).toBe(false);
    } finally {
      harness.close();
    }
  });

  test("[PUSH-CLIENT-017] drop espera baja remota, hace local una vez y persiste retry ante error", async () => {
    const order = [];
    const subscriptionCalls = { unsubscribe: [] };
    const existing = makeSubscription({
      applicationServerKey: vapidBytes(),
      calls: subscriptionCalls,
      onUnsubscribe: () => order.push("local"),
    });
    const harness = await loadingHarness({
      subscription: existing,
      fetchImpl: async (input) => {
        const path = new URL(input).pathname;
        order.push(path);
        if (path.endsWith("/unsubscribe/")) throw new TypeError("offline");
        return new Response("", { status: 200 });
      },
    });
    try {
      harness.window.localStorage.clear();
      harness.dispatchReady();
      await harness.flush();
      harness.button.click();
      await harness.flush(16);
      expect(order[0]).toBe("/api/subscribe/");
      expect(order).toContain("/api/unsubscribe/");
      expect(order.at(-1)).toBe("local");
      expect(subscriptionCalls.unsubscribe).toHaveLength(1);
      expect(harness.window.localStorage.getItem("mragentes:push-unsubscribe-retry")).toContain(existing.endpoint);
      expect(harness.button.getAttribute("aria-pressed")).toBe("false");
    } finally {
      harness.close();
    }
  });

  test("[PUSH-CLIENT-018] drop no deja fetch flotante ni muestra off antes de terminar", async () => {
    let release;
    const remote = new Promise((resolve) => { release = resolve; });
    const existing = makeSubscription({ applicationServerKey: vapidBytes() });
    const harness = await loadingHarness({
      subscription: existing,
      fetchImpl: async (input) => new URL(input).pathname.endsWith("/unsubscribe/") ? remote : new Response("", { status: 200 }),
    });
    try {
      harness.dispatchReady();
      await harness.flush();
      harness.button.click();
      await harness.flush();
      expect(harness.button.disabled).toBe(true);
      expect(harness.button.getAttribute("aria-pressed")).toBe("true");
      expect(harness.status.textContent).toMatch(/desactivando|procesando|esper/i);
      release(new Response("", { status: 200 }));
      await harness.flush(16);
      expect(harness.button.disabled).toBe(false);
      expect(harness.button.getAttribute("aria-pressed")).toBe("false");
    } finally {
      harness.close();
    }
  });
});
