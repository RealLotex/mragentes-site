import { JSDOM } from "jsdom";

import { readProjectFile } from "./target-loader.mjs";

export async function createPushClientHarness({
  api = "https://push.mragentes.test",
  vapid = "BAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
  userAgent = "Mozilla/5.0",
  platform = "Linux x86_64",
  maxTouchPoints = 0,
  standalone = false,
  notificationPermission = "default",
  requestPermissionResult = "granted",
  requestPermissionError = null,
  subscription = null,
  registerError = null,
  subscribeError = null,
  fetchImpl,
  withButton = true,
  withStatus = true,
  readyState = "complete",
} = {}) {
  const html = `<!doctype html><html><head>
    <meta name="push-api-url" content="${api}">
    <meta name="vapid-key" content="${vapid}">
  </head><body>
    ${withButton ? '<button type="button" data-push-btn hidden>Avisos</button>' : ""}
    ${withStatus ? '<p data-push-status aria-live="polite"></p>' : ""}
  </body></html>`;
  const dom = new JSDOM(html, {
    url: "https://mragentes.com.ar/notas/",
    runScripts: "outside-only",
    pretendToBeVisual: true,
  });
  const { window } = dom;
  const calls = {
    register: [],
    subscribe: [],
    unsubscribe: [],
    fetch: [],
    permission: [],
    listeners: [],
  };

  Object.defineProperty(window.document, "readyState", { configurable: true, value: readyState });
  Object.defineProperty(window.navigator, "userAgent", { configurable: true, value: userAgent });
  Object.defineProperty(window.navigator, "platform", { configurable: true, value: platform });
  Object.defineProperty(window.navigator, "maxTouchPoints", { configurable: true, value: maxTouchPoints });
  Object.defineProperty(window.navigator, "standalone", { configurable: true, value: standalone });
  window.matchMedia = () => ({ matches: standalone, addListener() {}, removeListener() {} });
  window.PushManager = class PushManager {};
  window.Notification = class Notification {};
  Object.defineProperty(window.Notification, "permission", {
    configurable: true,
    value: notificationPermission,
  });
  window.Notification.requestPermission = async () => {
    calls.permission.push({});
    if (requestPermissionError) throw requestPermissionError;
    Object.defineProperty(window.Notification, "permission", {
      configurable: true,
      value: requestPermissionResult,
    });
    return requestPermissionResult;
  };

  let currentSubscription = subscription;
  const registration = {
    pushManager: {
      async getSubscription() {
        return currentSubscription;
      },
      async subscribe(options) {
        calls.subscribe.push(options);
        if (subscribeError) throw subscribeError;
        currentSubscription = makeSubscription({
          endpoint: "https://push.example.test/new-subscription",
          applicationServerKey: options.applicationServerKey,
          calls,
          onUnsubscribe: () => { currentSubscription = null; },
        });
        return currentSubscription;
      },
    },
  };
  const serviceWorker = {
    async register(url, options) {
      calls.register.push({ url, options });
      if (registerError) throw registerError;
      return registration;
    },
  };
  Object.defineProperty(window.navigator, "serviceWorker", {
    configurable: true,
    value: serviceWorker,
  });

  window.fetch = async (input, init = {}) => {
    calls.fetch.push({ input: String(input), init });
    if (!fetchImpl) return new Response("", { status: 204 });
    return fetchImpl(input, init);
  };
  // jsdom does not consistently expose fetch classes; use Node's WHATWG ones.
  window.Response = globalThis.Response;
  window.Request = globalThis.Request;
  window.Headers = globalThis.Headers;
  window.atob = globalThis.atob;
  window.btoa = globalThis.btoa;

  let source = await readProjectFile("assets/js/push.js", "PUSH-CLIENT-HARNESS-001");
  const exposurePoint = "  if (document.readyState === \"loading\") {";
  if (!source.includes(exposurePoint)) {
    throw new Error("[PUSH-CLIENT-HARNESS-001] push.js no contiene el punto de instrumentación esperado");
  }
  source = source.replace(
    exposurePoint,
    `  window.__MR_PUSH_TEST__ = { meta, b64ToBytes, iosNeedsInstall, supported, keyMatches, init };\n${exposurePoint}`,
  );
  window.eval(`${source}\n//# sourceURL=assets/js/push.instrumented.js`);

  return {
    dom,
    window,
    document: window.document,
    button: window.document.querySelector("[data-push-btn]"),
    status: window.document.querySelector("[data-push-status]"),
    api: window.__MR_PUSH_TEST__,
    registration,
    calls,
    currentSubscription: () => currentSubscription,
    dispatchReady() {
      window.document.dispatchEvent(new window.Event("DOMContentLoaded"));
    },
    async flush(turns = 8) {
      for (let index = 0; index < turns; index += 1) await Promise.resolve();
    },
    close() {
      dom.window.close();
    },
  };
}

export function makeSubscription({
  endpoint = "https://push.example.test/subscription",
  applicationServerKey,
  calls = { unsubscribe: [] },
  unsubscribeResult = true,
  unsubscribeError = null,
  onUnsubscribe = () => {},
} = {}) {
  return {
    endpoint,
    options: applicationServerKey === undefined ? {} : { applicationServerKey },
    async unsubscribe() {
      calls.unsubscribe.push(endpoint);
      if (unsubscribeError) throw unsubscribeError;
      onUnsubscribe();
      return unsubscribeResult;
    },
    toJSON() {
      return {
        endpoint,
        expirationTime: null,
        keys: { p256dh: "public-key", auth: "auth-secret" },
      };
    },
  };
}
