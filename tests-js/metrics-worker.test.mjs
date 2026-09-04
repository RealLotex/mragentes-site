import { describe, expect, test } from "vitest";

import worker, { metricPoint } from "../workers/metrics/src/index.js";

function environment() {
  const points = [];
  return { points, env: { METRICS: { writeDataPoint: (point) => points.push(point) } } };
}

describe("Worker de métricas de MR Agentes", () => {
  test("[METRICS-001] registra compartir sin cookies ni identificadores", async () => {
    const { points, env } = environment();
    const response = await worker.fetch(new Request("https://mragentes.com.ar/api/metrics/v1/events", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Content-Length": "56" },
      body: JSON.stringify({ event: "share_whatsapp", path: "/notas/guia/" }),
    }), env);

    expect(response.status).toBe(204);
    expect(points).toEqual([metricPoint("share_whatsapp", "/notas/guia/")]);
    expect(points[0].indexes).toEqual([]);
  });

  test("[METRICS-002] rechaza eventos y rutas que puedan identificar o redirigir", async () => {
    const { points, env } = environment();
    const response = await worker.fetch(new Request("https://mragentes.com.ar/api/metrics/v1/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event: "click", path: "/notas/guia/?email=persona@example.com" }),
    }), env);

    expect(response.status).toBe(400);
    expect(points).toEqual([]);
  });

  test("[METRICS-003] atribuye la entrada social y redirige sólo al permalink canónico", async () => {
    const { points, env } = environment();
    const response = await worker.fetch(new Request("https://mragentes.com.ar/r/guia-practica?source=facebook"), env);

    expect(response.status).toBe(302);
    expect(response.headers.get("Location")).toBe("https://mragentes.com.ar/notas/guia-practica/");
    expect(points).toEqual([metricPoint("social_referral", "facebook:/notas/guia-practica/")]);
  });
});
