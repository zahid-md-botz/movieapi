/**
 * ZAHID MOVIE API — Cloudflare edge gateway.
 *
 * This Worker deliberately keeps the existing Railway application as the
 * single source of truth for API keys, quotas, SQLite playback tickets, admin
 * pages and the Python curl-cffi media relay. It forwards request/response
 * bodies as streams and never buffers video in Worker memory.
 */
const HOP_BY_HOP = new Set([
  'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
  'te', 'trailer', 'transfer-encoding', 'upgrade',
]);

function json(message, status = 503) {
  return new Response(JSON.stringify({
    status, success: false, creator: 'Zahid dev',
    code: 'EDGE_ORIGIN_UNAVAILABLE', message,
  }), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
      'access-control-allow-origin': '*',
    },
  });
}

function cleanHeaders(input, { request = false } = {}) {
  const headers = new Headers(input);
  for (const name of HOP_BY_HOP) headers.delete(name);
  headers.delete('host');
  if (request) headers.delete('content-length');
  return headers;
}

export default {
  async fetch(request, env) {
    let origin;
    try {
      origin = new URL(String(env.ORIGIN_URL || ''));
      if (origin.protocol !== 'https:' || origin.username || origin.password || origin.search || origin.hash) {
        return json('Cloudflare origin configuration is invalid.', 503);
      }
    } catch {
      return json('ORIGIN_URL must be the HTTPS Railway public domain.', 503);
    }

    const incoming = new URL(request.url);
    const target = new URL(incoming.pathname + incoming.search, origin);
    const headers = cleanHeaders(request.headers, { request: true });
    headers.delete('x-edge-secret');

    // These headers let the existing Railway app generate public short links
    // on the Cloudflare hostname instead of exposing its Railway origin URL.
    headers.set('x-forwarded-host', incoming.host);
    headers.set('x-forwarded-proto', incoming.protocol.slice(0, -1));
    headers.set('x-forwarded-port', incoming.port || (incoming.protocol === 'https:' ? '443' : '80'));

    // The origin rejects requests that do not carry this private shared secret.
    if (env.EDGE_SHARED_SECRET) headers.set('x-edge-secret', env.EDGE_SHARED_SECRET);

    const init = {
      method: request.method,
      headers,
      redirect: 'manual',
    };
    if (request.method !== 'GET' && request.method !== 'HEAD') init.body = request.body;

    try {
      const upstream = await fetch(new Request(target.toString(), init));
      const responseHeaders = cleanHeaders(upstream.headers);
      responseHeaders.set('cache-control', 'no-store');
      responseHeaders.set('x-content-type-options', 'nosniff');

      // Keep same-origin redirects on the public Worker hostname.
      const location = responseHeaders.get('location');
      if (location) {
        try {
          const redirected = new URL(location, origin);
          if (redirected.origin === origin.origin) {
            redirected.protocol = incoming.protocol;
            redirected.host = incoming.host;
            responseHeaders.set('location', redirected.toString());
          }
        } catch { /* Preserve a non-URL Location value unchanged. */ }
      }

      // Response.body is passed through directly: MP4 bytes, HLS manifests,
      // DASH manifests, Range/206 and Content-Range remain streaming responses.
      return new Response(request.method === 'HEAD' ? null : upstream.body, {
        status: upstream.status,
        statusText: upstream.statusText,
        headers: responseHeaders,
      });
    } catch (error) {
      console.error('Railway origin request failed:', error?.name || 'Error');
      return json('The Railway API origin is temporarily unavailable.', 502);
    }
  },
};
