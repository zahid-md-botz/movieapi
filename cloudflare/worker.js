const HOP_BY_HOP = new Set([
  'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
  'te', 'trailer', 'transfer-encoding', 'upgrade',
]);
const ALLOWED_MEDIA_HOSTS = [
  'hakunaymatata.com', 'aoneroom.com', 'histar.tv', 'cloudfront.net',
  'aisports.mobi', 'aisports.cc', 'moviebox.ph', 'movieboxhd.net',
  'inmoviebox.com',
];
const TOKEN_RE = /^[A-Za-z0-9_-]{24}$/;

function json(message, status = 503, code = 'EDGE_ERROR') {
  return new Response(JSON.stringify({
    status, success: false, creator: 'Zahid dev', code, message,
  }, null, 2), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
      'access-control-allow-origin': '*',
    },
  });
}

function safeOrigin(value) {
  try {
    const url = new URL(String(value || ''));
    if (url.protocol !== 'https:' || url.username || url.password || url.pathname !== '/' || url.search || url.hash) throw new Error();
    return url;
  } catch {
    throw new Error('ORIGIN_URL must be an HTTPS Railway origin');
  }
}

function safeMediaUrl(value) {
  const url = new URL(String(value || ''));
  const host = url.hostname.toLowerCase().replace(/\.$/, '');
  if (url.protocol !== 'https:' || url.username || url.password || (url.port && url.port !== '443') ||
      !ALLOWED_MEDIA_HOSTS.some(s => host === s || host.endsWith(`.${s}`))) throw new Error('Media host is not permitted');
  return url;
}

function requestHeaders(request, data) {
  const headers = new Headers();
  for (const [name, value] of Object.entries(data.headers || {})) {
    if (!/^[!#$%&'*+.^_`|~0-9A-Za-z-]+$/.test(name)) continue;
    if (/^(host|authorization|proxy-authorization|connection|content-length|transfer-encoding|range|accept-encoding)$/i.test(name)) continue;
    if (typeof value === 'string' && value.length <= 4096 && !/[\r\n]/.test(value)) headers.set(name, value);
  }
  headers.set('Accept-Encoding', 'identity');
  if (!headers.has('Accept')) headers.set('Accept', 'video/mp4,video/webm,application/octet-stream;q=0.9,*/*;q=0.8');
  if (!headers.has('Accept-Language')) headers.set('Accept-Language', 'en-US,en;q=0.9');
  if (!headers.has('Sec-Fetch-Dest')) headers.set('Sec-Fetch-Dest', 'video');
  if (!headers.has('Sec-Fetch-Mode')) headers.set('Sec-Fetch-Mode', 'no-cors');
  if (!headers.has('Sec-Fetch-Site')) headers.set('Sec-Fetch-Site', 'cross-site');
  const range = request.headers.get('Range');
  const ifRange = request.headers.get('If-Range');
  if (range) headers.set('Range', range);
  if (ifRange) headers.set('If-Range', ifRange);
  return headers;
}

function responseHeaders(upstream, download, filename) {
  const headers = new Headers();
  for (const name of ['accept-ranges', 'cache-control', 'content-length', 'content-range', 'content-type', 'etag', 'expires', 'last-modified']) {
    const value = upstream.headers.get(name);
    if (value) headers.set(name, value);
  }
  if (download && filename) {
    const clean = String(filename).replace(/[\r\n"\\]/g, '_').replace(/[^\x20-\x7e]/g, '_');
    headers.set('Content-Disposition', `attachment; filename="${clean}"`);
  } else if (filename) {
    const clean = String(filename).replace(/[\r\n"\\]/g, '_').replace(/[^\x20-\x7e]/g, '_');
    headers.set('Content-Disposition', `inline; filename="${clean}"`);
  }
  headers.set('Access-Control-Allow-Origin', '*');
  headers.set('Access-Control-Expose-Headers', 'Content-Range,Content-Length,Accept-Ranges,Content-Disposition,Content-Type');
  headers.set('Cache-Control', 'private, no-store');
  headers.set('X-Content-Type-Options', 'nosniff');
  return headers;
}

async function resolvePlayback(origin, token, secret) {
  const response = await fetch(new URL('/internal/edge-media', origin), {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-Edge-Secret': secret},
    body: JSON.stringify({token}),
  });
  if (!response.ok) return {error: await response.text().catch(() => ''), status: response.status};
  const payload = await response.json();
  return {data: payload.data};
}

async function fetchMedia(request, data) {
  let target = safeMediaUrl(data.url);
  let headers = requestHeaders(request, data);
  for (let attempt = 0; attempt < 6; attempt += 1) {
    const upstream = await fetch(target, {method: request.method === 'HEAD' ? 'HEAD' : 'GET', headers, redirect: 'manual'});
    if (![301, 302, 303, 307, 308].includes(upstream.status)) return upstream;
    const location = upstream.headers.get('location');
    if (!location) throw new Error('Media redirect has no location');
    const next = safeMediaUrl(new URL(location, target).href);
    if (next.hostname !== target.hostname) {
      const kept = new Headers();
      for (const name of ['user-agent', 'referer', 'origin', 'accept', 'accept-language']) {
        const value = headers.get(name); if (value) kept.set(name, value);
      }
      headers = kept;
    }
    target = next;
  }
  throw new Error('Too many media redirects');
}

export default {
  async fetch(request, env) {
    if (request.method === 'OPTIONS') return new Response(null, {status: 204, headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Headers': 'Range,If-Range,Content-Type,Authorization',
      'Access-Control-Allow-Methods': 'GET,HEAD,OPTIONS',
    }});
    const incoming = new URL(request.url);
    const match = incoming.pathname.match(/^\/media\/([A-Za-z0-9_-]{24})$/);
    if (!match) return json('Endpoint not found', 404, 'NOT_FOUND');
    if (!['GET', 'HEAD'].includes(request.method)) return json('Use GET or HEAD', 405, 'METHOD_NOT_ALLOWED');
    if (!env.EDGE_SHARED_SECRET) return json('EDGE_SHARED_SECRET is not configured', 503, 'EDGE_CONFIG_MISSING');
    let origin;
    try { origin = safeOrigin(env.ORIGIN_URL); } catch (error) { return json(error.message, 503, 'EDGE_CONFIG_INVALID'); }
    try {
      const resolved = await resolvePlayback(origin, match[1], env.EDGE_SHARED_SECRET);
      if (!resolved.data) return json('Playback link expired; request fresh sources', resolved.status || 401, 'PLAYBACK_EXPIRED');
      const upstream = await fetchMedia(request, resolved.data);
      if (!upstream.ok && upstream.status !== 416) {
        return json(`CDN returned HTTP ${upstream.status}`, 502, 'MEDIA_UPSTREAM_ERROR');
      }
      const type = upstream.headers.get('content-type') || '';
      if (/(?:text\/html|application\/(?:problem\+)?json)/i.test(type)) return json('CDN returned an error document instead of media', 502, 'MEDIA_UPSTREAM_ERROR');
      const headers = responseHeaders(upstream, incoming.searchParams.get('download') === '1', resolved.data.filename);
      return new Response(request.method === 'HEAD' ? null : upstream.body, {status: upstream.status, headers});
    } catch (error) {
      console.error('Cloudflare media edge failure:', error?.name || 'Error');
      return json('Media edge could not fetch the upstream source', 502, 'MEDIA_EDGE_FAILURE');
    }
  },
};
