import { afterEach, beforeEach, vi } from "vitest";

const originalFetch = globalThis.fetch;

beforeEach(() => {
  globalThis.fetch = vi.fn(async () => {
    throw new Error("[JS-NET-001] unexpected network call; inject a fake transport");
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  globalThis.fetch = originalFetch;
});
