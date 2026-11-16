# ZAHID MOVIE API — Cloudflare + Railway deployment (A to Z)

This deployment keeps the existing Railway Node.js application, SQLite key store, admin panel, MovieBox engine and private Python `curl-cffi` media relay. Cloudflare Worker is the public edge gateway. It forwards requests and response bodies as streams; it does not download or buffer the video.

The Railway domain remains the private origin. Users should use the Cloudflare Worker URL or the custom domain attached to the Worker.

## 0. Before starting

- Keep a backup of the current Railway project and its `/app/.data` volume.
- Do not delete the existing Railway service, volume, domain or variables.
- The supplied `.env` file has intentionally been removed from this ZIP. If its old `ADMIN_SECRET` was ever used, rotate it in Railway before deploying.
- Node.js 24 is required by this project.

## 1. Prepare the secrets

Generate two independent random values, each at least 32 characters:

- `ADMIN_SECRET`: admin authentication and signed playback tickets. Rotate the old value because the uploaded ZIP contained an `.env` file.
- `EDGE_SHARED_SECRET`: private authentication between Cloudflare Worker and Railway.

Do not reuse the same value for both. Do not put either value in Git, `wrangler.toml`, HTML or browser JavaScript. Keep the edge secret ready; add it to Railway only after the Worker has been deployed and tested, so the existing Railway domain does not go offline while you are setting up Cloudflare.

## 2. Update Railway first

1. Open the existing Railway project and select the existing MovieAPI service.
2. Open **Variables**.
3. Keep the current `ADMIN_SECRET`, or rotate it if it was exposed. Use a new random value of at least 32 characters.
4. Keep/add `DATA_DIR=/app/.data`.
5. Set `PUBLIC_BASE_URL=https://movieapi.ideapaid911.workers.dev`. This is the canonical public hostname for all generated `streamUrl`, `downloadUrl`, and short links. If you later attach a custom domain, update this variable to that exact HTTPS origin.
6. Keep any existing optional SMTP variables.
7. Confirm the existing Railway Volume is mounted at `/app/.data`. Do not remove it; it contains the SQLite key/quota/playback database.
8. Keep the existing Railway domain: `movieapi-production-59c04909.up.railway.app`.
9. Keep the service start command `npm start`, Dockerfile builder, and health check `/api/v3/health`.

At this first stage, leave `EDGE_SHARED_SECRET` unset in Railway. The updated app remains reachable on its current Railway domain while you create and test the Worker. The edge guard activates automatically when you later add the secret to Railway.

## 3. Push the updated project to GitHub

1. Extract the ZIP.
2. Open the `movieapi-main` folder (the folder containing `package.json`).
3. Replace the repository files with these updated files. Do not commit `.env`, `.data`, SQLite files, `node_modules`, or `.dev.vars`.
4. Commit and push to the same GitHub repository connected to Railway.
5. Wait for Railway deployment to finish.
6. Check Railway logs for:
   - `Chrome-impersonating HTTP/2 transport ready`
   - no missing `ADMIN_SECRET` or `DATA_DIR` errors.
7. Check `https://movieapi-production-59c04909.up.railway.app/api/v3/health`. Health should return JSON. The Railway domain is now origin-only for normal requests; only this health endpoint is intentionally left public.

## 4. Create a Cloudflare account

1. Open https://dash.cloudflare.com/sign-up.
2. Create an account and verify your email.
3. Open the Cloudflare dashboard.
4. You do not need to buy a domain to test the Worker. The free `workers.dev` hostname is enough for the first deployment.

## 5. Install Wrangler on your computer

Install Node.js 24 LTS if it is not already installed. Open a terminal in the extracted `movieapi-main` project folder and run:

```bash
node --version
npm --version
npx wrangler@4 --version
```

If the Wrangler command asks to install the package, accept it. Then log in:

```bash
npx wrangler@4 login
```

A browser window opens. Sign in to Cloudflare and authorize Wrangler.

## 6. Configure the Worker secret

Use the `EDGE_SHARED_SECRET` value you generated. You will add this exact value to Railway after the Worker passes its initial tests:

```bash
npx wrangler@4 secret put EDGE_SHARED_SECRET
```

Paste the secret when prompted. The command does not print it back.

The Railway origin URL is already set in `wrangler.toml`:

```toml
ORIGIN_URL = "https://movieapi-production-59c04909.up.railway.app"
```

If Railway ever gives you a different domain, update this value before deploying the Worker.

## 7. Deploy the Cloudflare Worker

From the folder containing `wrangler.toml`, run:

```bash
npx wrangler@4 deploy
```

At the end Wrangler prints a URL similar to:

```text
https://zahid-movieapi.YOUR-SUBDOMAIN.workers.dev
```

Save this URL. It is the initial public API and website address.

## 8. Test the Worker before buying/connecting a custom domain

Replace `YOUR-WORKER-URL` with the URL Wrangler printed:

```text
https://YOUR-WORKER-URL/
https://YOUR-WORKER-URL/docs
https://YOUR-WORKER-URL/api/v3/health
https://YOUR-WORKER-URL/api/v3/catalog
```

Test a search with the public key:

```bash
curl -H "Authorization: Bearer zahidmovieapi" \
  "https://YOUR-WORKER-URL/api/v3/search/avengers"
```

If Cloudflare shows `502 Bad gateway` with `Host Error`, the Worker cannot get a healthy response from the Railway origin; changing media URLs cannot repair a stopped/crashed Railway deployment. Check Railway Deployments and Logs first, confirm the service is Active, and open the Railway `/api/v3/health` URL directly. The Python relay must log `Chrome-impersonating HTTP/2 transport ready`.

A healthy `/health` response only proves the API process is running. Search must return actual items before moving on to media tests. At this point, the Worker secret is set but Railway has not yet enabled the edge-only guard.

## 9. Lock the Railway origin behind the Worker

After the Worker URL has passed the health and search tests:

1. Open Railway → existing MovieAPI service → Variables.
2. Add `EDGE_SHARED_SECRET` using the exact same value already stored in Cloudflare Worker Secrets.
3. Save/redeploy.
4. Test the Worker URL again; it must still work.
5. Test the Railway domain `/api/v3/catalog`; it should now return HTTP 403 `EDGE_ONLY`, while `/api/v3/health` remains available for Railway health checks.

This confirms normal traffic goes through Cloudflare and direct origin requests are blocked.

## 10. Buy a domain and connect it to Cloudflare

You may buy a domain from any registrar. A `.com` domain is a straightforward choice; compare the first-year price and renewal price before paying. Do not buy hosting or a VPS for this API — Railway already hosts the application.

After buying the domain:

1. In Cloudflare dashboard choose **Add a site**.
2. Enter your domain, for example `zahidmovieapi.com` (use the domain you actually purchased).
3. Select the Free plan if offered.
4. Cloudflare scans/imports DNS records. Review them carefully.
5. Cloudflare shows two assigned nameservers.
6. Open the domain registrar's **Nameservers / DNS** settings.
7. Replace the registrar's default nameservers with the exact two nameservers Cloudflare displayed.
8. Save and wait until Cloudflare shows the domain as **Active**.
9. Do not copy example nameservers from a tutorial; use only the two assigned to your account.

If the domain already has email or an existing website, preserve its MX, TXT and other required DNS records before changing nameservers. Do not delete records you do not recognize.

## 11. Attach the custom domain to the Worker

1. In Cloudflare dashboard open **Workers & Pages**.
2. Select `zahid-movieapi`.
3. Open **Settings** or **Domains & Routes** (dashboard wording may vary).
4. Choose **Add** → **Custom Domain**.
5. Enter the hostname you want, for example `api.zahidmovieapi.com` (replace with your real domain).
6. Confirm. Cloudflare creates/manages the required DNS route and certificate.
7. Wait until the custom domain status is active.

Use this custom hostname for your API and website. Do not point it directly to Railway. Cloudflare must attach it to the Worker.

## 12. Verify the full media flow

1. Open `/api/v3/search/<movie-name>` with a valid API key.
2. Choose a result and call `/api/v3/info/<id>`.
3. Call `/api/v3/sources/<id>`.
4. Confirm `streamUrl` and `downloadUrl` use your Cloudflare hostname, not the Railway hostname.
5. Open `streamUrl` in Chrome. Confirm video starts, seek works, and a byte-range request returns `206` when the upstream supports ranges.
6. Open `downloadUrl`. Confirm the browser downloads actual media bytes and the filename has the right extension.
7. Test a series episode using `?season=1&episode=1`.
8. Test HLS/DASH separately. HLS/DASH manifests are adaptive streams, not a single MP4 file; they require a compatible player and do not receive a fake MP4 download link.

Example range test:

```bash
curl -i -H "Range: bytes=0-1023" \
  "PASTE_A_FRESH_STREAM_URL_HERE" -o range-test.bin
```

A `206 Partial Content` response with a valid `Content-Range` is expected when the CDN supports byte ranges. Do not reuse an expired source URL; request `/sources` again.

## 13. Troubleshooting

- **Worker returns 502:** check `ORIGIN_URL`, Railway deployment status and Railway logs.
- **Railway returns 403 EDGE_ONLY:** the Worker secret and Railway `EDGE_SHARED_SECRET` do not match, or the request is going directly to Railway.
- **Railway fails to start:** confirm `ADMIN_SECRET` and `DATA_DIR=/app/.data` are configured; confirm the persistent volume is mounted.
- **Search works but media returns 426:** Cloudflare is connected, but the upstream CDN is rejecting the media request. Inspect Railway `[media-proxy]` and `media_transport.relay` logs. A Worker gateway cannot by itself change the Railway-to-CDN egress decision. Verify the actual upstream status, request headers, source expiry, CDN redirect host and Railway region before claiming it is fixed.
- **Stream works but download is unavailable:** select an MP4/WebM/TS single-file source. HLS `.m3u8` and DASH `.mpd` are manifests, not direct single-file downloads.
- **Worker hostname still shows Railway links:** ensure the Worker forwards `x-forwarded-host` and that the updated `src/local-modern.js` is deployed on Railway.

## Important architecture note

This version intentionally uses Cloudflare as a streaming edge gateway and keeps the existing SQLite key/quota/playback database on Railway. That avoids silently migrating or resetting the existing API-key/admin system. Unlike the reference project's Durable Object design, this version does not require a Cloudflare KV namespace or Durable Object for the gateway. The Railway Python media relay remains responsible for upstream CDN connections.
