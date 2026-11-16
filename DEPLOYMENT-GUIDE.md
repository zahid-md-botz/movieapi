# Movie API — Railway backend + Cloudflare frontend

## Status before you deploy

This is a source-based deployment preparation, **not a claim of production readiness**.
Local Python startup, contract tests and a Cloudflare dry-run have been checked.
Live homepage and detail metadata returned real provider data. Search returned no
matches during the initial probe; the adapter now attempts the native provider
instead of accepting that empty web response as verified search. Native fallback
requires the signing variable below. Full-movie playback, downloads, trailer bytes,
poster-image loading, manga-provider availability and live cross-cloud operation
must still pass your deployment acceptance checks.

Docker files are provided, but Docker builds cannot be executed in this environment.
Build them on Railway or a Docker-capable machine before accepting the release.

## Architecture

* Cloudflare Worker: public pages, compatibility API gateway, authentication/quota,
  Durable Object short playback links, signed trailer links, KV and existing UI.
* Railway Python: MovieBox engine, catalog/search/detail/anime processing, manga
  parsing/ZIP creation, upstream communication and bounded media relay.
* Browser API requests go to the same Cloudflare origin. The Worker calls Railway
  privately with `x-relay-secret`. Do not put relay credentials in browser JS.
* Manifest link rewriting stays in the Worker because its URLs are public gateway
  URLs and it owns playback authorization. Media bytes originate on Railway.
* Original legacy Node utilities remain for compatibility, but are **not** the
  Railway production entry point. Use Wrangler for the real frontend locally.
* Existing retired routes (live/schedule/upcoming/test-channels) remain retired;
  this release does not restore features already disabled by the original router.

## 1. Railway — recommended Python-only deployment

1. Extract the ZIP. The `movieapi/` folder is the repository root.
2. Push its contents to your own Git repository and connect that repository to
   your existing Railway service. No account was connected or deployed by this work.
3. In service settings set **Root Directory** to `/python-origin`.
4. Set the Railway config file to `/python-origin/railway.toml` (config paths are
   repository-relative). The build context is the Python directory.
5. Select the Dockerfile builder if it is not detected. Use `Dockerfile` in that
   directory. It uses official `python:3.13-slim-bookworm`; Python is installed in
   the base image and checked at build time. Dependencies install at build time.
6. Clear any old Start Command override, especially the `python -c` source-bundle
   command. The image CMD is `python local.py`, binding `0.0.0.0:$PORT`.
7. Add the variables below through Railway's Variables interface.
8. Deploy, inspect build logs and runtime logs, then generate/copy your service's
   HTTPS public domain in Railway networking settings.
9. Check `curl --fail https://YOUR-RAILWAY-SERVICE.up.railway.app/health`.
   This proves process health only, not provider availability.

Alternative: keep Root Directory `/` and use the root `railway.toml`, which uses
`python-origin/Dockerfile.root` with the repository as build context. Do not mix
that Dockerfile with the Python-only build context.

### Railway variables

| Name | Required | Meaning and source |
|---|---|---|
| `RELAY_SECRET` | Yes | Generate a strong random secret in your password manager; use exactly the same value in Cloudflare. Never commit it. |
| `MOVIEBOX_SIGNING_KEY_B64` | Yes for native search/details/streams/captions | Base64-encoded native protocol signing key from your authorized provider configuration. In the supplied `moviebox-final.js`, decoding the outer Base64 layer of `SECRET_DEFAULT_B64` yields this value. Do not decode the resulting Base64 a second time when setting this variable. No value has been invented or copied into the new Python source. |
| `PORT` | Railway supplies it | Listener port; defaults to 3000 outside Railway. Do not hardcode a different public port. |
| `PYTHONUNBUFFERED` | Set in image | `1`, immediate runtime logging. |
| `PYTHONDONTWRITEBYTECODE` | Set in image | `1`, no runtime bytecode files. |

`MOVIEAPI_SOURCE_BUNDLE` is obsolete. No database, API-key ledger URL, Node runtime,
SMTP configuration, provider ZIP path or Replit URL is required on Railway.
The Python provider implementation is now shipped as `python-origin/engine.py`.
The health endpoint intentionally remains usable without a provider session;
missing signing configuration will prevent native operations, not invent data.

### Commands

From the extracted repository root:

```sh
# On a Docker-capable machine; do not put real secret values into shell history.
docker build -t movieapi-origin ./python-origin
docker run --rm -p 3000:3000 --env-file /secure/path/movieapi.env movieapi-origin
# Alternative root build:
docker build -f python-origin/Dockerfile.root -t movieapi-origin .
```

For Railway CLI, install/login using Railway's official instructions, then from
the repository root run `railway link`, select the existing service, and
`railway up`. Configure the root/build settings above first. Alternatively,
push to the linked Git branch. `railway logs` shows runtime logs.

## 2. Cloudflare Worker, not Pages

Keep the existing Worker deployment: it uses Workers Static Assets, KV and the
`ApiKeyLedger` SQLite Durable Object. A static Pages-only upload is not sufficient.

From `movieapi/`:

```sh
corepack enable
pnpm install --frozen-lockfile
pnpm exec wrangler login
pnpm exec wrangler secret put ADMIN_SECRET
pnpm exec wrangler secret put RELAY_SECRET
pnpm exec wrangler deploy --dry-run
# Only after reviewing config and acceptance checks:
pnpm exec wrangler deploy
```

Update `wrangler.toml`:

```toml
[vars]
ENGINE_RELAY_URL = "https://YOUR-RAILWAY-SERVICE.up.railway.app"
```

Replace that placeholder with **your actual Railway URL**, without `/health`,
`/internal/moviebox`, a trailing path, credentials or an invented hostname.
The source does not have a separate `MEDIA_URL`: both metadata and media use
`ENGINE_RELAY_URL`. Keep the Worker main file `runtime-worker.js`.

### Cloudflare bindings, variables and secrets

| Name | Location | Purpose |
|---|---|---|
| `ENGINE_RELAY_URL` | `[vars]` | Your real Railway HTTPS origin. Required. |
| `RELAY_SECRET` | Secret | Same secret as Railway. Required. |
| `MOVIE_RELAY_SECRET` | Secret, legacy alternative | Used only if `RELAY_SECRET` is absent. Do not configure conflicting values. |
| `ADMIN_SECRET` | Secret | Strong independent admin and playback-ticket signing secret. Required. Rotating it invalidates encrypted playback tickets. |
| `KV_STORE` | KV binding | Existing KV namespace; keep its ID to preserve data. |
| `API_KEY_LEDGER` | Durable Object binding | Existing SQLite API key/quota and short-link store. Keep class, binding, name and migration history unchanged. |
| `ASSETS` | Static assets binding | `./public`, bundled by Wrangler. |
| `OWNER_WHATSAPP` | Optional variable | Existing legacy key-request contact override. Current modern support-contact code has its own preserved business contact. |

The existing account/namespace IDs were preserved. If this is a different
Cloudflare account, change `account_id`, create a namespace with
`pnpm exec wrangler kv namespace create KV_STORE`, and use its returned ID.
That creates **empty storage**, not a migration of old users/keys. Do not change
IDs in the existing account just to make deployment succeed. Back up current
configuration and data before any migration.

`CF_WORKER_URL`, `CF_WORKER_API_KEY`, `WORKER_ADMIN_SECRET`, `KEY_LEDGER_URL`,
`MOVIEBOX_PROXY_URL`, `PROXY_LIST`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`,
`SMTP_PASS`, `PYTHON`, `PYTHONPATH`, `NODE_ENV`, and `CLOUDFLARE_API_TOKEN`
occur in legacy local tools, tests or deployment tooling. They are **not**
required for this Python + Worker runtime. Wrangler login avoids needing an
API token in source. `STORAGE_LABEL` is computed by the Worker.

## 3. Local tests and acceptance checks

Python 3.13 and Node 24+:

```sh
python -m pip install -r python-origin/requirements.txt
python -m unittest discover -s python-origin -p 'test_*.py' -v
pnpm test
pnpm exec wrangler deploy --dry-run
```

The tests explicitly use fixtures and local servers. Fixtures are never served
as production responses. Test passing is not evidence of CDN acceptance.

On a securely configured machine, export your real `RELAY_SECRET` and
`MOVIEBOX_SIGNING_KEY_B64` through your secret manager, then:

```sh
python python-origin/local.py
# Separately, bounded live-provider smoke checks:
python python-origin/verify_live.py
```

For live deployment checks, set shell variables `RAILWAY_URL`, `WORKER_URL`,
`RELAY_SECRET`, and `API_KEY` securely. Never use an admin secret as a public API key.

```sh
curl --fail "$RAILWAY_URL/health"
curl --fail "$RAILWAY_URL/internal/moviebox" \
  -H "x-relay-secret: $RELAY_SECRET" -H 'Content-Type: application/json' \
  --data '{"action":"home","params":{}}'
curl --fail "$WORKER_URL/api/v3/health"
curl --fail "$WORKER_URL/api/v3/homepage" -H "X-API-Key: $API_KEY"
curl --fail "$WORKER_URL/api/v3/search/Interstellar" -H "X-API-Key: $API_KEY"
curl --fail "$WORKER_URL/api/v3/anime" -H "X-API-Key: $API_KEY"
```

Use a real subject ID returned by the homepage/search, not an invented ID:

```sh
curl --fail "$WORKER_URL/api/v3/info/$SUBJECT_ID" -H "X-API-Key: $API_KEY"
curl --fail "$WORKER_URL/api/v3/sources/$SUBJECT_ID?season=0&episode=0" \
  -H "X-API-Key: $API_KEY"
```

Check title, description, genres and poster URL against the provider. Load the
poster separately. Sources should return short `streamUrl` and `downloadUrl`.
Copy those into secure shell variables, then verify:

```sh
curl --fail --max-time 30 --max-filesize 1024 -D headers.txt \
  -H 'Range: bytes=0-1023' "$STREAM_URL" -o first.bin
curl --fail --max-time 30 --max-filesize 1024 -D seek-headers.txt \
  -H 'Range: bytes=1048576-1049599' "$STREAM_URL" -o seek.bin
curl --fail --head "$STREAM_URL"
curl --fail --head "$DOWNLOAD_URL"
```

Require HTTP 206, exactly 1024 bytes and matching Content-Range for both range
tests. Verify HEAD has no body and the correct media length; download has
Content-Disposition. Actually play and seek in a browser before accepting
playback. Test returned trailer `videoAddress.url` independently. HLS/DASH need
manifest, key, initialization and segment checks; a successful manifest alone
does not verify playback. Do not assume all CDN hosts/codecs are supported.

Test manga home/search/genres/details/chapter and both ZIP download endpoints.
Image fetching is restricted to the observed `rosyscans.id` and
`img.rosyscans.id` hosts, including redirects. Unknown CDNs fail explicitly;
do not weaken this into an unrestricted URL proxy.

Recheck quotas, disabled/deleted keys, expired links and short links after Worker
redeploy and Railway restart. Test `OPTIONS` preflight with Range and If-Range.
The origin deliberately does not allow browsers to call private endpoints;
CORS is handled by the Worker and secrets stay server-side.

## Troubleshooting and limits

* `python: command not found`: wrong builder/image or stale Start Command override.
  Check that the Docker build log shows Python 3.13 and the supplied Dockerfile.
* 401 internal request: relay secrets differ or header is missing.
* 502 search/native operations: configure the signing key, check provider/region
  availability. Do not bypass provider restrictions or substitute fake results.
* 503 media: eight-transfer limit reached. The existing bounded transport queues
  eight chunks per transfer; media is not downloaded wholesale into RAM.
* Manga archives use temporary disk with a 256 MiB total/20 MiB-per-image cap.
  They fail on missing images rather than silently delivering incomplete ZIPs.
* `/health` success does not establish MovieBox, manga or CDN availability.
* Live provider errors are sanitized; do not log bearer tokens, signed URLs,
  cookies, raw upstream errors or relay secrets while investigating.
* Static sample JSON remains documentation data, never a live API fallback.

Reference: https://docs.railway.com/builds/dockerfiles
and https://developers.cloudflare.com/workers/wrangler/commands/
