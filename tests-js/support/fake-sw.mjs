import vm from "node:vm";
import { readProjectFile } from "./target-loader.mjs";

function responseClone(value) {
  return value?.clone ? value.clone() : value;
}

export class FakeCache {
  constructor(name, fetchImpl) {
    this.name = name;
    this.fetchImpl = fetchImpl;
    this.entries = new Map();
    this.calls = [];
  }

  key(input) {
    if (typeof input === "string") return new URL(input, "https://mragentes.com.ar").href;
    return input.url;
  }

  async add(input) {
    this.calls.push({ operation: "add", input });
    const url = this.key(input);
    const response = await this.fetchImpl(url);
    if (!response.ok) throw new Error(`precache failed: ${response.status}`);
    this.entries.set(url, responseClone(response));
  }

  async match(input) {
    this.calls.push({ operation: "match", input });
    const value = this.entries.get(this.key(input));
    return value ? responseClone(value) : undefined;
  }

  async put(input, response) {
    this.calls.push({ operation: "put", input, response });
    this.entries.set(this.key(input), responseClone(response));
  }
}

export class FakeCacheStorage {
  constructor(fetchImpl) {
    this.fetchImpl = fetchImpl;
    this.stores = new Map();
    this.deleted = [];
  }

  async open(name) {
    if (!this.stores.has(name)) this.stores.set(name, new FakeCache(name, this.fetchImpl));
    return this.stores.get(name);
  }

  async keys() {
    return [...this.stores.keys()];
  }

  async delete(name) {
    this.deleted.push(name);
    return this.stores.delete(name);
  }

  async match(input) {
    for (const cache of this.stores.values()) {
      const response = await cache.match(input);
      if (response) return response;
    }
    return undefined;
  }
}

function createExtendableEvent(extra = {}) {
  const waited = [];
  return {
    ...extra,
    waited,
    waitUntil(promise) {
      waited.push(Promise.resolve(promise));
    },
    async drain() {
      return Promise.allSettled(waited);
    },
  };
}

export async function createServiceWorkerHarness({
  fetchImpl = async () => new Response("asset", { status: 200 }),
  clients = [],
  now = Date.parse("2026-08-26T12:00:00.000Z"),
} = {}) {
  const handlers = new Map();
  const calls = {
    skipWaiting: 0,
    claim: 0,
    showNotification: [],
    openWindow: [],
    matchAll: [],
    fetch: [],
  };
  const routedFetch = async (input, init) => {
    calls.fetch.push({ input, init });
    return fetchImpl(input, init);
  };
  const caches = new FakeCacheStorage(routedFetch);
  const clientApi = {
    async claim() { calls.claim += 1; },
    async matchAll(options) {
      calls.matchAll.push(options);
      return clients;
    },
    async openWindow(url) {
      calls.openWindow.push(url);
      return { url };
    },
  };
  const registration = {
    async showNotification(title, options) {
      calls.showNotification.push({ title, options });
    },
    pushManager: {
      async subscribe() {
        throw new Error("[PUSH-SW-FAKE-001] inject pushManager.subscribe for this test");
      },
    },
  };
  const self = {
    location: new URL("https://mragentes.com.ar/sw.js"),
    registration,
    clients: clientApi,
    async skipWaiting() { calls.skipWaiting += 1; },
    addEventListener(type, handler) {
      handlers.set(type, handler);
    },
  };
  class FixedDate extends Date {
    static now() { return now; }
  }
  const quietConsole = { log() {}, warn() {}, error() {}, info() {} };
  const context = vm.createContext({
    self,
    clients: clientApi,
    caches,
    fetch: routedFetch,
    URL,
    Request,
    Response,
    Headers,
    console: quietConsole,
    Date: FixedDate,
    Promise,
    setTimeout,
    clearTimeout,
  });
  const source = await readProjectFile("static/sw.js", "PUSH-SW-HARNESS-001");
  vm.runInContext(source, context, { filename: "static/sw.js" });

  return {
    context,
    self,
    clients: clientApi,
    registration,
    handlers,
    caches,
    calls,
    source,
    event: createExtendableEvent,
    async dispatch(type, event = createExtendableEvent()) {
      const handler = handlers.get(type);
      if (!handler) return { handled: false, event };
      const returned = handler(event);
      if (returned && typeof returned.then === "function") await returned;
      return { handled: true, event };
    },
    fetchEvent(request) {
      let responsePromise;
      return createExtendableEvent({
        request,
        respondWith(value) { responsePromise = Promise.resolve(value); },
        response: () => responsePromise,
      });
    },
    pushEvent(data) {
      return createExtendableEvent({
        data: data === undefined
          ? null
          : {
              json() {
                if (data instanceof Error) throw data;
                return data;
              },
            },
      });
    },
  };
}
