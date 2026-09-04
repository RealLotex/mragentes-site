import { describe, expect, test } from "vitest";

import worker, { metricValues } from "../workers/metrics/src/index.js";

function environment() {
  const calls = [];
  const tasks = [];
  const env = {
    METRICS_DB: {
      prepare: (sql) => ({
        bind: (...values) => ({
          run: async () => { calls.push({ sql, values }); return { success: true }; },
        }),
      }),
    },
  };
  const ctx = { waitUntil: (promise) => tasks.push(promise) };
  return { calls, tasks, env, ctx };
}

describe("Worker de métricas de MR Agentes", () => {
  test("[METRICS-001] registra compartir sin cookies ni identificadores", async () => {
    const { calls, tasks, env, ctx } = environment();
    const response = await worker.fetch(new Request("https://mragentes.com.ar/api/metrics/v1/events", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Content-Length": "56" },
      body: JSON.stringify({ event: "share_whatsapp", path: "/notas/guia/" }),
    }), env, ctx);

    expect(response.status).toBe(204);
    await Promise.all(tasks);
    expect(calls).toHaveLength(1);
    expect(calls[0].sql).toMatch(/INSERT INTO metric_events/i);
    expect(calls[0].values.slice(0, 2)).toEqual(metricValues("share_whatsapp", "/notas/guia/").slice(0, 2));
  });

  test("[METRICS-002] rechaza eventos y rutas que puedan identificar o redirigir", async () => {
    const { calls, tasks, env, ctx } = environment();
    const response = await worker.fetch(new Request("https://mragentes.com.ar/api/metrics/v1/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event: "click", path: "/notas/guia/?email=persona@example.com" }),
    }), env, ctx);

    expect(response.status).toBe(400);
    expect(calls).toEqual([]);
    expect(tasks).toEqual([]);
  });

  test("[METRICS-003] atribuye la entrada social y redirige sólo al permalink canónico", async () => {
    const { calls, tasks, env, ctx } = environment();
    const response = await worker.fetch(new Request("https://mragentes.com.ar/r/guia-practica?source=facebook"), env, ctx);

    expect(response.status).toBe(302);
    expect(response.headers.get("Location")).toBe("https://mragentes.com.ar/notas/guia-practica/");
    await Promise.all(tasks);
    expect(calls[0].values.slice(0, 2)).toEqual(["social_referral", "facebook:/notas/guia-practica/"]);
  });
});
