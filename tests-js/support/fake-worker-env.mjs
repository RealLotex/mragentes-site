import assert from "node:assert/strict";

function clone(value) {
  return value === undefined ? undefined : structuredClone(value);
}

export class FakeClock {
  constructor(now = Date.parse("2026-08-26T12:00:00.000Z")) {
    this.current = now;
  }

  now = () => this.current;

  advance(milliseconds) {
    this.current += milliseconds;
    return this.current;
  }
}

export class FakeKV {
  constructor({ clock = new FakeClock(), pageSize = Infinity } = {}) {
    this.clock = clock;
    this.pageSize = pageSize;
    this.entries = new Map();
    this.calls = [];
    this.failures = new Map();
  }

  failNext(operation, error = new Error(`FakeKV ${operation} failure`)) {
    const queued = this.failures.get(operation) ?? [];
    queued.push(error);
    this.failures.set(operation, queued);
  }

  #maybeFail(operation) {
    const queued = this.failures.get(operation);
    if (!queued?.length) return;
    const error = queued.shift();
    if (!queued.length) this.failures.delete(operation);
    throw error;
  }

  #pruneOne(key) {
    const entry = this.entries.get(key);
    if (entry?.expiresAt !== undefined && entry.expiresAt <= this.clock.now()) {
      this.entries.delete(key);
      return undefined;
    }
    return entry;
  }

  async put(key, value, options = {}) {
    this.#maybeFail("put");
    this.calls.push({ operation: "put", key, value, options: clone(options) });
    const expiresAt = options.expirationTtl === undefined
      ? undefined
      : this.clock.now() + Number(options.expirationTtl) * 1_000;
    this.entries.set(String(key), {
      value: typeof value === "string" ? value : String(value),
      metadata: clone(options.metadata),
      expiresAt,
    });
  }

  async get(key, options = {}) {
    this.#maybeFail("get");
    this.calls.push({ operation: "get", key, options: clone(options) });
    const entry = this.#pruneOne(String(key));
    if (!entry) return null;
    if (options === "json" || options?.type === "json") return JSON.parse(entry.value);
    if (options === "arrayBuffer" || options?.type === "arrayBuffer") {
      return new TextEncoder().encode(entry.value).buffer;
    }
    return entry.value;
  }

  async getWithMetadata(key, options = {}) {
    this.#maybeFail("getWithMetadata");
    const entry = this.#pruneOne(String(key));
    if (!entry) return { value: null, metadata: null };
    const value = options === "json" || options?.type === "json"
      ? JSON.parse(entry.value)
      : entry.value;
    return { value, metadata: clone(entry.metadata) ?? null };
  }

  async delete(key) {
    this.#maybeFail("delete");
    this.calls.push({ operation: "delete", key });
    this.entries.delete(String(key));
  }

  async list({ cursor, limit, prefix = "" } = {}) {
    this.#maybeFail("list");
    this.calls.push({ operation: "list", cursor, limit, prefix });
    for (const key of [...this.entries.keys()]) this.#pruneOne(key);
    const keys = [...this.entries.keys()]
      .filter((key) => key.startsWith(prefix))
      .sort((a, b) => a.localeCompare(b));
    const start = cursor ? Number(Buffer.from(cursor, "base64url").toString("utf8")) : 0;
    const effectiveLimit = Math.min(limit ?? Infinity, this.pageSize);
    const page = keys.slice(start, start + effectiveLimit);
    const next = start + page.length;
    const listComplete = next >= keys.length;
    return {
      keys: page.map((name) => ({ name, metadata: clone(this.entries.get(name)?.metadata) })),
      cursor: listComplete ? "" : Buffer.from(String(next), "utf8").toString("base64url"),
      list_complete: listComplete,
    };
  }
}

export class FetchRouter {
  constructor() {
    this.routes = [];
    this.calls = [];
  }

  respond(method, matcher, response) {
    this.routes.push({ method: method.toUpperCase(), matcher, response });
    return this;
  }

  reject(method, matcher, error) {
    return this.respond(method, matcher, () => Promise.reject(error));
  }

  fetch = async (input, init = {}) => {
    const request = input instanceof Request ? input : new Request(input, init);
    const call = {
      request,
      method: request.method,
      url: request.url,
      headers: Object.fromEntries(request.headers.entries()),
    };
    this.calls.push(call);
    const route = this.routes.find((candidate) => {
      if (candidate.method !== request.method) return false;
      if (typeof candidate.matcher === "string") return candidate.matcher === request.url;
      if (candidate.matcher instanceof RegExp) return candidate.matcher.test(request.url);
      return candidate.matcher(request);
    });
    assert.ok(route, `[JS-NET-ROUTER-001] no fake route for ${request.method} ${request.url}`);
    const value = typeof route.response === "function"
      ? await route.response(request, call)
      : route.response;
    return value instanceof Response ? value : new Response(value?.body ?? "", value);
  };
}

export class ExecutionContextRecorder {
  constructor() {
    this.promises = [];
    this.passThrough = false;
  }

  waitUntil(promise) {
    this.promises.push(Promise.resolve(promise));
  }

  passThroughOnException() {
    this.passThrough = true;
  }

  async drain() {
    const settled = await Promise.allSettled(this.promises);
    this.promises.length = 0;
    return settled;
  }
}

export class FakeDurableStorage {
  constructor(seed = {}) {
    this.data = new Map(Object.entries(seed));
    this.calls = [];
    this.transactionDepth = 0;
    this.sqlStatements = [];
    this.sql = {
      exec: (statement, ...bindings) => {
        this.sqlStatements.push({ statement, bindings: clone(bindings) });
        return { toArray: () => [], one: () => null, raw: () => [] };
      },
    };
  }

  async get(key) {
    this.calls.push({ operation: "get", key });
    return clone(this.data.get(key));
  }

  async put(key, value) {
    this.calls.push({ operation: "put", key, value: clone(value) });
    this.data.set(key, clone(value));
  }

  async delete(key) {
    this.calls.push({ operation: "delete", key });
    return this.data.delete(key);
  }

  async list({ prefix = "" } = {}) {
    return new Map(
      [...this.data.entries()]
        .filter(([key]) => key.startsWith(prefix))
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, value]) => [key, clone(value)]),
    );
  }

  async transaction(callback) {
    this.transactionDepth += 1;
    const snapshot = clone([...this.data.entries()]);
    try {
      return await callback(this);
    } catch (error) {
      this.data = new Map(snapshot);
      throw error;
    } finally {
      this.transactionDepth -= 1;
    }
  }
}

export class FakeDurableObjectState {
  constructor(storage = new FakeDurableStorage()) {
    this.storage = storage;
    this.blockConcurrencyWhileCalls = [];
  }

  blockConcurrencyWhile(callback) {
    const promise = Promise.resolve().then(callback);
    this.blockConcurrencyWhileCalls.push(promise);
    return promise;
  }
}

export function jsonRequest(url, body, { method = "POST", headers = {} } = {}) {
  return new Request(url, {
    method,
    headers: { "Content-Type": "application/json", ...headers },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export function validSubscription(endpoint = "https://push.example.test/subscription/abc") {
  return {
    endpoint,
    expirationTime: null,
    keys: {
      p256dh: "BEl62iUYgUivxIkv69yViEuiBIa40HI3xJjs7RVXRr2NoHXtohKFh5HjrAblB0Uq-kEqZUY_7YxutkAq1tYtLqI",
      auth: "BTBZMqHH6r4Tts7J_aSIgg",
    },
  };
}
