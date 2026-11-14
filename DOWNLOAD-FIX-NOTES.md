# Download / streaming transport patch

## What changed

- Kept the existing Node API routes, MovieBox metadata engine, API-key/quota SQLite store, signed playback tickets, website and admin UI.
- Added a private Python media relay inside the same Railway container. It binds only to `127.0.0.1`, so it is not a public arbitrary-URL proxy.
- The relay uses the reference project's `curl-cffi` Chrome impersonation + HTTP/2 transport for CDN media requests.
- Preserves upstream `200`, `206` and `416` statuses and media headers, forwards byte ranges, validates redirect hosts, and streams chunks without buffering the whole video.
- Caps active media transfers at eight and each transfer's queue at eight chunks.
- Existing `/api/v3/stream/:token` and `/api/v3/download/:token` URLs remain in place. Movie, series episodes and anime continue to use their existing source routes and signed URLs. `downloadUrl` is now exposed only for single-file MP4/WebM/TS sources; HLS/DASH remain streaming manifests and are not falsely offered as a direct MP4 download.

## Required Railway change

The included `railway.toml` now selects the Dockerfile builder. Railway must build this commit with `Dockerfile`, not an old custom Nixpacks build command. Keep `npm start`, `ADMIN_SECRET`, `DATA_DIR=/app/.data`, and the existing volume mounted at `/app/.data`. Do not delete the volume or regenerate the admin secret during this patch.

## Verification status

- JavaScript syntax checks: passed.
- Python syntax compilation: passed.
- Full Node test suite: not executed successfully in the packaging environment because dependency installation timed out; the container had Node 22 while the project requires Node 24. Railway's Docker image supplies Node 24 and installs dependencies during image build.
- Real CDN download / WhatsApp send: must be verified after Railway deploy with a fresh source URL, because this requires live upstream access and the user's Railway runtime.
