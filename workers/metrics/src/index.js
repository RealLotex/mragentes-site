const ALLOWED_EVENTS = new Set(["share_native", "share_copy", "share_whatsapp"]);
const ALLOWED_SOURCES = new Set(["facebook", "instagram"]);
const ORIGIN = "https://mragentes.com.ar";
const MAX_BODY_BYTES = 512;
const REACTIONS_PATH = "/api/metrics/v1/reactions/";
const VISITOR_ID = /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/;

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

export function metricValues(event, dimension, now = new Date()) {
  return [event, dimension, now.toISOString()];
}

async function recordMetric(db, event, dimension) {
  await db
    .prepare("INSERT INTO metric_events (event, dimension, occurred_at) VALUES (?1, ?2, ?3)")
    .bind(...metricValues(event, dimension))
    .run();
}

async function noteReaction(request, db, slug) {
  if (!validSlug(slug)) return new Response("not found", { status: 404 });
  const visitor = request.headers.get("X-Note-Visitor") || "";
  const headers = { "Cache-Control": "no-store" };

  const total = () => db.prepare("SELECT likes FROM note_reaction_totals WHERE slug = ?1").bind(slug);
  if (request.method === "GET") {
    if (VISITOR_ID.test(visitor)) {
      const current = await db.prepare(
        "SELECT COALESCE((SELECT likes FROM note_reaction_totals WHERE slug = ?1), 0) AS likes, " +
        "EXISTS(SELECT 1 FROM note_reactions WHERE slug = ?1 AND visitor = ?2) AS liked"
      ).bind(slug, visitor).first();
      return Response.json({ likes: current.likes, liked: Boolean(current.liked) }, { headers });
    }
    return Response.json({ likes: (await total().first())?.likes ?? 0 }, { headers });
  }

  if (request.method !== "PUT" && request.method !== "DELETE") {
    return new Response(null, { status: 405, headers: { ...headers, Allow: "GET, PUT, DELETE" } });
  }
  if (!cors(request)["Access-Control-Allow-Origin"]) return new Response(null, { status: 403, headers });
  if (!VISITOR_ID.test(visitor)) return new Response(null, { status: 400, headers });

  const liked = request.method === "PUT";
  const change = db.prepare(liked
    ? "INSERT OR IGNORE INTO note_reactions (slug, visitor) VALUES (?1, ?2)"
    : "DELETE FROM note_reactions WHERE slug = ?1 AND visitor = ?2"
  ).bind(slug, visitor);
  const [, snapshot] = await db.batch([change, total()]);
  return Response.json({ likes: snapshot.results[0]?.likes ?? 0, liked }, { headers });
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname.startsWith(REACTIONS_PATH)) {
      let slug;
      try { slug = decodeURIComponent(url.pathname.slice(REACTIONS_PATH.length)); }
      catch { return new Response(null, { status: 404 }); }
      return noteReaction(request, env.METRICS_DB, slug);
    }
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
      ctx.waitUntil(recordMetric(env.METRICS_DB, payload.event, payload.path));
      return noContent(request);
    }

    if (request.method === "GET" && url.pathname.startsWith("/r/")) {
      const encodedSlug = url.pathname.slice(3);
      let slug;
      try { slug = decodeURIComponent(encodedSlug); } catch { return new Response("not found", { status: 404 }); }
      const source = url.searchParams.get("source");
      if (!validSlug(slug) || !ALLOWED_SOURCES.has(source)) return new Response("not found", { status: 404 });
      const destination = new URL("/notas/" + encodeURIComponent(slug) + "/", ORIGIN);
      ctx.waitUntil(recordMetric(env.METRICS_DB, "social_referral", source + ":" + destination.pathname));
      return Response.redirect(destination.toString(), 302);
    }

    return new Response("not found", { status: 404, headers: { "Cache-Control": "no-store" } });
  },
};
