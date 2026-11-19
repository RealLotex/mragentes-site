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

  test("[METRICS-004] cuenta reacciones por nota y usa una transacción para aplicar y devolver una", async () => {
    const path = "https://mragentes.com.ar/api/metrics/v1/reactions/an%C3%A1lisis-ia";
    const visitor = "f84875b4-0b12-4cea-82ae-4aee8615a1fd";
    const headers = { Origin: "https://mragentes.com.ar", "X-Note-Visitor": visitor };
    const operations = [];
    const env = { METRICS_DB: {
      prepare: (sql) => ({ bind: (...values) => ({ sql, values, first: async () => ({ likes: 2 }) }) }),
      batch: async (sql) => { operations.push(sql); return [{ success: true }, { results: [{ likes: 3 }] }]; },
    } };
    const get = await worker.fetch(new Request(path), env);
    expect(await get.json()).toEqual({ likes: 2 });
    const put = await worker.fetch(new Request(path, { method: "PUT", headers }), env);
    expect(await put.json()).toEqual({ likes: 3, liked: true });
    const drop = await worker.fetch(new Request(path, { method: "DELETE", headers }), env);
    expect(await drop.json()).toEqual({ likes: 3, liked: false });
    expect(operations[0][0]).toMatchObject({ sql: expect.stringContaining("INSERT OR IGNORE"), values: ["análisis-ia", visitor] });
    expect(operations[1][0]).toMatchObject({ sql: expect.stringContaining("DELETE FROM"), values: ["análisis-ia", visitor] });
    expect(operations.flat().filter(({ sql }) => /^SELECT /.test(sql))).toHaveLength(2);
  });

  test("[METRICS-005] rechaza origen, identificador y slug inválidos antes de tocar la base", async () => {
    const parent = "https://mragentes.com.ar/api/metrics/v1/reactions/";
    const valid = { Origin: "https://mragentes.com.ar", "X-Note-Visitor": "f84875b4-0b12-4cea-82ae-4aee8615a1fd" };
    const env = { METRICS_DB: { prepare() { throw new Error("No debe consultar D1"); } } };
    for (const [url, headers, status] of [
      [parent + "guia", { ...valid, Origin: "https://example.com" }, 403],
      [parent + "guia", { ...valid, "X-Note-Visitor": "un-identificador-invalido" }, 400],
      [parent + "arch%2Fivo", valid, 404],
    ]) {
      expect((await worker.fetch(new Request(url, { method: "PUT", headers }), env)).status).toBe(status);
    }
  });
});
