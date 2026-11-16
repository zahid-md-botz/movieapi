import test from 'node:test';
import assert from 'node:assert/strict';
import worker from './cloudflare/worker.js';

test('Cloudflare gateway forwards Range and private edge headers without buffering response', async () => {
  const originalFetch = globalThis.fetch;
  let captured;
  globalThis.fetch = async request => {
    captured = request;
    return new Response(Uint8Array.from([1, 2, 3, 4]), {
      status: 206,
      headers: {
        'content-type': 'video/mp4',
        'content-length': '4',
        'content-range': 'bytes 0-3/100',
        'accept-ranges': 'bytes',
        'content-disposition': 'attachment; filename="sample.mp4"',
      },
    });
  };
  try {
    const request = new Request('https://api.example.com/api/v3/stream/abc?x=1', {
      headers: { Range: 'bytes=0-3', 'If-Range': '"etag"', 'X-Edge-Secret': 'spoofed' },
    });
    const response = await worker.fetch(request, {
      ORIGIN_URL: 'https://movieapi-production-59c04909.up.railway.app',
      EDGE_SHARED_SECRET: 'private-edge-secret-value-1234567890',
    });
    assert.equal(new URL(captured.url).host, 'movieapi-production-59c04909.up.railway.app');
    assert.equal(new URL(captured.url).pathname, '/api/v3/stream/abc');
    assert.equal(new URL(captured.url).search, '?x=1');
    assert.equal(captured.headers.get('range'), 'bytes=0-3');
    assert.equal(captured.headers.get('if-range'), '"etag"');
    assert.equal(captured.headers.get('x-forwarded-host'), 'api.example.com');
    assert.equal(captured.headers.get('x-edge-secret'), 'private-edge-secret-value-1234567890');
    assert.equal(response.status, 206);
    assert.equal(response.headers.get('content-length'), '4');
    assert.equal(response.headers.get('content-range'), 'bytes 0-3/100');
    assert.match(response.headers.get('content-disposition'), /sample\.mp4/);
    assert.deepEqual([...new Uint8Array(await response.arrayBuffer())], [1, 2, 3, 4]);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('Cloudflare gateway rejects invalid/non-HTTPS origins', async () => {
  const response = await worker.fetch(new Request('https://api.example.com/'), { ORIGIN_URL: 'http://localhost:3000' });
  assert.equal(response.status, 503);
});
