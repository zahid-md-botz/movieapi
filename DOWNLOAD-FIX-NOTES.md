# Download / streaming transport patch
..
## What changed

- Kept the existing Node API routes, MovieBox metadata engine, API-key/quota SQLite store, signed playback tickets, website and admin UI.
- Added a private Python media relay inside the same Railway container. It binds only to `127.0.0.1`, so it is not a public arbitrary-URL proxy.
- The relay uses the reference project's `curl-cffi` Chrome impersonation + HTTP/2 transport for CDN media requests.
- Preserves upstream `200`, `206` and `416` statuses and media headers, forwards `Range` / `If-Range`, validates redirect hosts, and streams chunks without buffering the whole video.
- A media source URL now has two explicit response modes: `/download/:token` returns `Content-Disposition: attachment`; `/stream/:token` returns inline playback and infers `video/mp4`, `video/webm`, `video/mp2t`, HLS, or DASH MIME types when the CDN only says `application/octet-stream`.
- HTTP/2 connection failures retry once using HTTP/1.1. Real upstream HTTP rejections are not silently treated as a successful media response.
- 502 diagnostics now write a request ID, upstream hostname, status, and safe error detail to Railway logs without logging signed URL query strings or cookies.
- Caps active media transfers at eight and each transfer's queue at eight chunks.
- Existing `/api/v3/stream/:token` and `/api/v3/download/:token` URLs remain in place. Movie, series episodes and anime continue to use their existing source routes and signed URLs. `downloadUrl` is now exposed only for single-file MP4/WebM/TS sources; HLS/DASH remain streaming manifests and are not falsely offered as a direct MP4 download.

## Required Railway change

The included `railway.toml` now selects the Dockerfile builder. Railway must build this commit with `Dockerfile`, not an old custom Nixpacks build command. Keep `npm start`, `ADMIN_SECRET`, `DATA_DIR=/app/.data`, and the existing volume mounted at `/app/.data`. Do not delete the volume or regenerate the admin secret during this patch.

## Verification status

- JavaScript syntax checks: passed.
- Python syntax compilation: passed.
- Full Node test suite: not executed successfully in the packaging environment because dependency installation timed out; the container had Node 22 while the project requires Node 24. Railway's Docker image supplies Node 24 and installs dependencies during image build.
- Full Node test suite: attempted, but could not run in the packaging container because npm dependencies are not installed (`cheerio` / `undici` missing); no test failures are being represented as passed.
- Real CDN download / Chrome playback / WhatsApp send: must be verified after Railway deploy with a fresh source URL, because this requires live upstream access and the user's Railway runtime. The exact live 502 can only be pinned to a CDN rejection versus relay transport failure from the new Railway diagnostic log.
