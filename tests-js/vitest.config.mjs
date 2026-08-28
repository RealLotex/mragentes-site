import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests-js/**/*.test.mjs"],
    setupFiles: ["./tests-js/setup.mjs"],
    environment: "node",
    globals: false,
    passWithNoTests: false,
    testTimeout: 5_000,
    hookTimeout: 5_000,
    restoreMocks: true,
    clearMocks: true,
    unstubGlobals: true,
  },
});
