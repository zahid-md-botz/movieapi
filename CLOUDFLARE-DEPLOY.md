# Cloudflare Media Edge Setup

This repository includes a Cloudflare Worker that resolves short playback tokens through the Railway API and fetches the signed MovieBox CDN media from Cloudflare's edge. Railway remains the API, key/quota store and token authority; the Worker handles MP4/HLS/DASH media streaming so CDN requests do not originate from Railway.

## Cloudflare setup

The repository is configured for automatic deployment from `wrangler.toml`. In the Cloudflare Worker project, add this secret:

```text
EDGE_SHARED_SECRET=<one random value, 32+ characters>
```

Set `ORIGIN_URL` in `wrangler.toml` to the public Railway URL. If the Railway domain changes, update that value and redeploy the Worker.

After the Worker deploys, copy its HTTPS URL, for example:

```text
https://zahid-movieapi-edge.<account>.workers.dev
```

## Railway variables

Set these variables in the Railway service:

```text
ADMIN_SECRET=<existing 32+ character secret>
DATA_DIR=/app/.data
EDGE_SHARED_SECRET=<exactly the same value as the Worker secret>
PUBLIC_BASE_URL=https://<your-worker>.workers.dev
```

Do not put `ADMIN_SECRET` in Cloudflare. The Worker only needs `EDGE_SHARED_SECRET` to call Railway's private token-resolver endpoint.

## Verify

1. Deploy the Worker and confirm its `workers.dev` URL responds.
2. Redeploy Railway after setting `EDGE_SHARED_SECRET` and `PUBLIC_BASE_URL`.
3. Call Railway `/api/v3/sources/<movie-id>` with an API key.
4. Confirm returned `streamUrl` starts with the Cloudflare Worker URL and uses `/media/<24-character-token>`.
5. Request that URL with `Range: bytes=0-1023`. A working response is `206 Partial Content` with `Content-Range` and video bytes.
6. For downloads, use the returned `downloadUrl`; it adds `?download=1` and streams with `Content-Disposition: attachment`.

If `streamUrl` still points to `movieapi-production-...up.railway.app`, Railway is missing either `PUBLIC_BASE_URL` or `EDGE_SHARED_SECRET`. If the Worker returns `EDGE_CONFIG_INVALID`, update `ORIGIN_URL` in `wrangler.toml`. If it returns `PLAYBACK_EXPIRED`, request fresh sources.
