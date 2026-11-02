// Server-side only. Serves the two files over 25 MiB from R2; all else -> static assets.
const LARGE = {
  "/runtime.css": ["runtime.css", "text/css; charset=utf-8"],
  "/fonts/embedding-lookup.woff2": ["embedding-lookup.woff2", "font/woff2"],
};
export default {
  async fetch(req, env) {
    const url = new URL(req.url), hit = LARGE[url.pathname];
    if (!hit || !["GET", "HEAD"].includes(req.method)) return env.ASSETS.fetch(req);
    const obj = await env.LARGE.get(hit[0], { onlyIf: req.headers, range: req.headers });
    if (!obj) return new Response("Not found", { status: 404 });
    const h = new Headers({ "content-type": hit[1], etag: obj.httpEtag, "accept-ranges": "bytes",
      "cache-control": url.searchParams.has("v") ? "public, max-age=31536000, immutable"
        : hit[1].startsWith("font/") ? "public, max-age=86400" : "public, max-age=300",
      "x-content-type-options": "nosniff", "content-security-policy": "script-src 'none'; object-src 'none'" });
    if (!("body" in obj)) return new Response(null, { status: 304, headers: h }); // If-None-Match matched
    let status = 200;
    if (obj.range && req.headers.has("range")) {
      const off = obj.range.offset ?? obj.size - obj.range.suffix, len = obj.range.length ?? obj.size - off;
      h.set("content-range", `bytes ${off}-${off + len - 1}/${obj.size}`); status = 206; h.set("content-length", len);
    } else h.set("content-length", obj.size);
    return new Response(req.method === "HEAD" ? null : obj.body, { status, headers: h });
  },
};
