# ZAHID MOVIE API — Railway deployment .

## Architecture

One Railway service runs the website, API, MovieBox metadata engine, SQLite key/quota/playback store, and a private localhost Python media relay. A Cloudflare Worker is the public media edge: it resolves short playback tokens through Railway and fetches signed CDN media from Cloudflare instead of Railway. The Node API handles routes and signed download tickets. The relay remains available as a direct fallback and for local testing.

## Deploy

1. Extract this ZIP and commit the contents of the `movieapi` folder to the repository root (do not add another nested folder).
2. Railway builds with the included `Dockerfile`; keep the start command `npm start`.
3. Set Railway variables:
   - `ADMIN_SECRET`: unique random value, at least 32 characters.
   - `DATA_DIR`: `/app/.data`.
   - `EDGE_SHARED_SECRET`: a different random value, exactly matching the Cloudflare Worker secret.
   - `PUBLIC_BASE_URL`: the Cloudflare Worker HTTPS URL.
   - `SUPPORT_EMAIL`: `myweb615265@gmail.com` (optional).
4. Attach a Railway Volume mounted at `/app/.data`. It stores API keys, quotas and playback sessions.
5. Keep one replica for the SQLite volume setup, deploy, and retain the existing Railway domain.

Deploy the Worker using [`CLOUDFLARE-DEPLOY.md`](CLOUDFLARE-DEPLOY.md). The Python media relay runs inside the same Railway container and listens only on `127.0.0.1:8765`; the Worker is preferred for public playback when `PUBLIC_BASE_URL` and `EDGE_SHARED_SECRET` are configured.

## Download and streaming endpoints

Use `/api/v3/sources/:id` for movies. For series, request `/api/v3/episodes/:id`, then `/api/v3/sources/:id?season=1&episode=1` for each selected episode. Anime uses `/api/v3/anime/sources/:id?season=1&episode=1`.

Each source returns `streamUrl`, available `downloadUrl` values, `filename`, and source variants. `downloadUrl` is provided only for single-file formats (MP4/WebM/TS), never for HLS/DASH manifests. Open it with GET to receive the actual media bytes with `Content-Disposition: attachment` (browser direct download). Use `streamUrl` for in-browser playback: it is returned inline and generic CDN MIME types are normalized to `video/mp4`, `video/webm`, etc. when the source URL identifies that format. The URLs are short-lived (six hours in the current implementation); request fresh sources after expiry. `Range`, `If-Range`, and `HEAD` are supported for media URLs.

The download endpoint returns the actual upstream format. MP4 sources download as MP4. HLS (`.m3u8`) and DASH (`.mpd`) are manifests, not a single MP4 file; select an MP4 source when one is available. This API does not transcode HLS/DASH into MP4.

## WhatsApp bot usage

After obtaining a source response, select a source with `format: mp4` where possible and use its `downloadUrl`. The bot should GET that URL as a stream and send the resulting bytes as `video/mp4` (or as a document if the file is too large for the bot's normal video-send path). For a series, repeat per episode and send each episode separately. Do not fetch an expired source URL; call the relevant `/sources` endpoint again.

## Verify after deploy

1. `/api/v3/health` — Node API and persistent storage health.
2. `/docs` — endpoint documentation.
3. Request a movie's sources and open its `downloadUrl` in a browser.
4. Test `Range: bytes=0-1023`; expect `206` and a `Content-Range` header when the upstream supports ranges.
5. Test a series episode and an anime episode separately.
6. Check Railway logs for `[media-relay] Chrome-impersonating HTTP/2 transport ready`.
7. If a media URL still returns 502, search logs for `[media-proxy] request=...` and the matching `media_transport.relay` log. The log records the CDN hostname, upstream status, and error class without printing signed query strings or cookies. HTTP/2 connection failures retry once using HTTP/1.1.

A healthy API health-check does not guarantee that MovieBox currently offers a playable source for every title. If the upstream CDN rejects Railway egress or the signed source expires, request fresh sources and inspect the returned HTTP status in Railway logs.

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `ADMIN_SECRET` | Yes | Protects admin operations and signs playback tickets. |
| `DATA_DIR` | Yes | Persistent SQLite directory; use `/app/.data`. |
| `EDGE_SHARED_SECRET` | With Cloudflare | Shared secret used only by the Worker token resolver. |
| `PUBLIC_BASE_URL` | With Cloudflare | Worker HTTPS origin used for generated stream/download links. |
| `SUPPORT_EMAIL` | No | Public support contact. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM` | No | Optional email delivery configuration. |
| `MEDIA_RELAY_PORT` | No | Private relay port; default `8765`. |
| `PYTHON_BIN` | No | Python executable; Docker default `/opt/venv/bin/python`. |
