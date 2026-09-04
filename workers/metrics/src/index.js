const ALLOWED_EVENTS = new Set(["share_native", "share_copy", "share_whatsapp"]);
const ALLOWED_SOURCES = new Set(["facebook", "instagram"]);
const ORIGIN = "https://mragentes.com.ar";
const MAX_BODY_BYTES = 512;

function cors(request) {
  const origin = request.headers.get("Origin");
  return origin === ORIGIN || origin === "https://www.mragentes.com.ar"
    ? { "Access-Control-Allow-Origin": origin, "Vary": "Origin" }
    : {};
}

function noContent(request) {
  return new Response(null, {
    status: 204,
    headers: { ...cors(request), "Cache-Control": "no-store" },
  });
}

function validPath(path) {
  return typeof path === "string"
    && path.startsWith("/notas/")
    && path.length <= 180
    && !path.includes("?")
    && !path.includes("#");
}

function validSlug(slug) {
  return /^[\p{L}0-9-]{1,160}$/u.test(slug);
}

export function metricPoint(event, dimension) {
  return { indexes: [], blobs: [event, dimension], doubles: [1] };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS" && url.pathname === "/api/metrics/v1/events") {
      return new Response(null, {
        status: 204,
        headers: {
          ...cors(request),
          "Access-Control-Allow-Methods": "POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type",
          "Access-Control-Max-Age": "86400",
          "Cache-Control": "no-store",
        },
      });
    }

    if (request.method === "POST" && url.pathname === "/api/metrics/v1/events") {
      const size = Number(request.headers.get("Content-Length") || "0");
      if (size > MAX_BODY_BYTES) return new Response("payload too large", { status: 413, headers: cors(request) });
      let payload;
      try {
        payload = await request.json();
      } catch {
        return new Response("invalid JSON", { status: 400, headers: cors(request) });
      }
      if (!ALLOWED_EVENTS.has(payload?.event) || !validPath(payload?.path)) {
        return new Response("invalid event", { status: 400, headers: cors(request) });
      }
      env.METRICS.writeDataPoint(metricPoint(payload.event, payload.path));
      return noContent(request);
    }

    if (request.method === "GET" && url.pathname.startsWith("/r/")) {
      const encodedSlug = url.pathname.slice(3);
      let slug;
      try { slug = decodeURIComponent(encodedSlug); } catch { return new Response("not found", { status: 404 }); }
      const source = url.searchParams.get("source");
      if (!validSlug(slug) || !ALLOWED_SOURCES.has(source)) return new Response("not found", { status: 404 });
      const destination = new URL("/notas/" + encodeURIComponent(slug) + "/", ORIGIN);
      env.METRICS.writeDataPoint(metricPoint("social_referral", source + ":" + destination.pathname));
      return Response.redirect(destination.toString(), 302);
    }

    return new Response("not found", { status: 404, headers: { "Cache-Control": "no-store" } });
  },
};
