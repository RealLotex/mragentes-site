import { afterEach, beforeEach, describe, expect, test as vitestTest, vi } from "vitest";
import { JSDOM } from "jsdom";
import { createPushClientHarness } from "./support/fake-dom.mjs";
import { readProjectFile } from "./support/target-loader.mjs";
import { tracedTest } from "./support/trace-test.mjs";

const test = tracedTest(vitestTest);
const DISMISS = "mragentes:push-prompt-dismissed";
const SESSION = "mragentes:push-prompt-seen";
const closed = [];

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "Date"] });
  vi.setSystemTime(new Date("2026-10-29T12:00:00Z"));
});
afterEach(() => {
  closed.splice(0).forEach((close) => close());
  vi.useRealTimers();
});

async function mount(window) {
  window.document.body.insertAdjacentHTML("beforeend", await readProjectFile("layouts/partials/push-prompt.html", "PUSH-PROMPT-HARNESS-001"));
  window.setTimeout = (callback, delay) => setTimeout(callback, delay);
  window.clearTimeout = (timer) => clearTimeout(timer);
  window.Date.now = () => Date.now();
  window.eval(await readProjectFile("assets/js/push-prompt.js", "PUSH-PROMPT-HARNESS-001"));
  return {
    panel: window.document.querySelector("[data-push-prompt]"),
    activate: window.document.querySelector("[data-push-prompt-activate]"),
    dismiss: window.document.querySelector("[data-push-prompt-dismiss]"),
    status: window.document.querySelector("[data-push-prompt-status]"),
  };
}

async function harness({ on = false, pending = false, hidden = false, permission = "default", unsupported = false, dismissed = null, seen = false, blockedStorage = false } = {}) {
  const dom = new JSDOM('<button data-push-btn aria-pressed="' + on + '">Avisos</button><p data-push-status></p>', {
    url: "https://mragentes.com.ar/", runScripts: "outside-only", pretendToBeVisual: true,
  });
  closed.push(() => dom.window.close());
  const { window } = dom;
  Object.defineProperty(window.document, "readyState", { configurable: true, value: "complete" });
  const footer = window.document.querySelector("[data-push-btn]");
  footer.hidden = hidden;
  footer.disabled = pending;
  window.Notification = { permission, requestPermission: vi.fn() };
  if (unsupported) delete window.Notification;
  if (dismissed !== null) window.localStorage.setItem(DISMISS, dismissed);
  if (seen) window.sessionStorage.setItem(SESSION, "1");
  if (blockedStorage) {
    for (const storage of ["localStorage", "sessionStorage"]) {
      Object.defineProperty(window, storage, { configurable: true, value: {
        getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); },
      } });
    }
  }
  const view = await mount(window);
  return { window, footer, ...view };
}

describe("Invitación para activar avisos", () => {
  test("[PUSH-PROMPT-001] aparece después de leer sin pedir permiso ni mover el foco", async () => {
    const h = await harness();
    h.footer.focus();
    await vi.advanceTimersByTimeAsync(9_999);
    expect(h.panel.hidden).toBe(true);
    await vi.advanceTimersByTimeAsync(1);
    expect(h.panel.hidden).toBe(false);
    expect(h.panel.textContent).toContain("Tu competencia ya usa IA.");
    expect(h.panel.textContent).toContain("Activá las notificaciones para mantenerte actualizado");
    expect(h.window.Notification.requestPermission).not.toHaveBeenCalled();
    expect(h.window.document.activeElement).toBe(h.footer);
    expect(h.panel.getAttribute("aria-modal")).toBe("false");
  });

  test("[PUSH-PROMPT-002] no invita con avisos activos, bloqueados, pendientes o no disponibles", async () => {
    for (const options of [{ on: true }, { pending: true }, { hidden: true }, { permission: "denied" }, { unsupported: true }, { seen: true }]) {
      const h = await harness(options);
      await vi.advanceTimersByTimeAsync(20_000);
      expect(h.panel.hidden, JSON.stringify(options)).toBe(true);
    }
  });

  test("[PUSH-PROMPT-003] cerrar respeta siete días y Escape restaura el foco", async () => {
    const h = await harness();
    h.footer.focus();
    await vi.advanceTimersByTimeAsync(10_000);
    h.dismiss.focus();
    h.window.document.dispatchEvent(new h.window.KeyboardEvent("keydown", { key: "Escape" }));
    expect(h.panel.hidden).toBe(true);
    expect(h.window.document.activeElement).toBe(h.footer);
    const dismissed = h.window.localStorage.getItem(DISMISS);
    expect(dismissed).toBeTruthy();
    const later = await harness({ dismissed });
    await vi.advanceTimersByTimeAsync(20_000);
    expect(later.panel.hidden).toBe(true);
    vi.setSystemTime(Date.now() + 8 * 24 * 60 * 60 * 1000);
    const nextWeek = await harness({ dismissed });
    await vi.advanceTimersByTimeAsync(10_000);
    expect(nextWeek.panel.hidden).toBe(false);
  });

  test("[PUSH-PROMPT-004] activa mediante el cliente existente y espera confirmación remota", async () => {
    let release;
    const network = new Promise((resolve) => { release = resolve; });
    const h = await createPushClientHarness({ readyState: "loading", fetchImpl: () => network });
    closed.push(() => h.close());
    const view = await mount(h.window);
    h.dispatchReady();
    await h.flush();
    await vi.advanceTimersByTimeAsync(10_000);
    expect(view.panel.hidden).toBe(false);
    expect(h.calls.permission).toHaveLength(0);
    view.activate.click();
    await h.flush();
    expect(h.calls.permission).toHaveLength(1);
    expect(h.calls.subscribe).toHaveLength(1);
    expect(view.activate.disabled).toBe(true);
    expect(view.panel.hidden).toBe(false);
    release(new Response("", { status: 201 }));
    await h.flush(20);
    expect(h.button.getAttribute("aria-pressed")).toBe("true");
    expect(view.panel.hidden).toBe(true);
  });

  test("[PUSH-PROMPT-005] conserva el error y permite reintentar sin anunciar un alta falsa", async () => {
    const h = await createPushClientHarness({ readyState: "loading", fetchImpl: async () => new Response("", { status: 500 }) });
    closed.push(() => h.close());
    const view = await mount(h.window);
    h.dispatchReady();
    await h.flush();
    await vi.advanceTimersByTimeAsync(10_000);
    view.activate.click();
    await h.flush(24);
    expect(view.panel.hidden).toBe(false);
    expect(view.activate.disabled).toBe(false);
    expect(view.status.textContent).toMatch(/No se pudo/);
    expect(h.button.getAttribute("aria-pressed")).toBe("false");
    expect(h.calls.unsubscribe).toHaveLength(1);
  });

  test("[PUSH-PROMPT-006] tolera almacenamiento bloqueado y no reaparece al cerrarlo", async () => {
    const h = await harness({ blockedStorage: true });
    await vi.advanceTimersByTimeAsync(10_000);
    expect(h.panel.hidden).toBe(false);
    h.dismiss.click();
    h.footer.disabled = true;
    h.footer.disabled = false;
    await vi.advanceTimersByTimeAsync(20_000);
    expect(h.panel.hidden).toBe(true);
  });
});
