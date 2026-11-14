# ZAHID MOVIE API — Railway deployment

## Architecture

One Railway Node.js service runs the website, API, MovieBox engine, admin panel and streaming routes. No Cloudflare account, Worker, Python sidecar, external quota ledger or Render service is required.

The API-key, quota and playback-session store uses SQLite. Attach a Railway persistent volume or the database will be lost when the service is redeployed/recreated.

## GitHub upload

1. Extract this ZIP.
2. Create a new GitHub repository and upload the contents of the `movieapi` folder (not an extra nested ZIP folder).
3. Do not upload `.env`, `.data/`, SQLite files, `node_modules/`, or any old cache. `.gitignore` excludes them.

## Railway setup

1. Railway → **New Project** → **Deploy from GitHub Repo** → select this repository.
2. Open the service → **Settings**. Build uses Nixpacks and `npm install`; start command is `npm start`. Node.js 24 is selected by `.node-version` and `package.json`.
3. Open **Variables** and add:
   - `ADMIN_SECRET` = a unique random secret of at least 32 characters. Generate one locally with `openssl rand -hex 32`; never publish it.
   - `DATA_DIR` = `/app/.data`
   - `SUPPORT_EMAIL` = `myweb615265@gmail.com`
4. Open **Volumes** → **Add Volume**. Set mount path exactly to `/app/.data`. Keep this volume attached to this service. It stores API keys, usage counters and playback-session records.
5. Deploy. Railway health check is configured for `/api/v3/health`.
6. Open **Settings → Networking → Generate Domain**. Railway will provide the live domain. You can connect a custom domain later.

## Important

- Do not set `KEY_LEDGER_URL`; the app uses its own SQLite database on the Railway volume.
- Do not add Cloudflare Worker variables or deploy any Worker.
- Do not upload old `.data` or `.wrangler` contents. The database initializes cleanly on first start and creates a fresh public documentation key.
- Do not run multiple replicas against the same SQLite database. Keep one running replica for this single-volume SQLite setup.
- Railway usage is not unlimited free hosting. Check your plan's current credit, volume and outbound bandwidth usage, especially for video streaming.
- The requested domain is not embedded as a fixed host. Source/download links are generated from the incoming Railway request host. Documentation examples use `YOUR-RAILWAY-DOMAIN` as a placeholder until Railway assigns the domain.
- Email delivery is disabled until a valid SMTP provider is configured. The support email is displayed as the contact address; setting it alone does not send mail.

## First checks

After deploy, open:

- `/api/v3/health` — service and storage status
- `/api/v3/catalog` — endpoint catalog
- `/docs` — API documentation
- `/admin` — admin UI

Then test a real search, details request, source extraction, byte-range stream and download using a valid API key. Health status alone does not prove the upstream MovieBox provider is responding or that a media host accepts Railway egress.

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `ADMIN_SECRET` | Yes | Protects admin operations and internal routes; use 32+ random characters. |
| `DATA_DIR` | Yes on Railway | Must match the mounted volume path `/app/.data`. |
| `SUPPORT_EMAIL` | No | Public support contact. |
| `PROXY_LIST` | No | Optional comma-separated trusted HTTP(S) proxy URLs. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM` | No | Optional email delivery configuration. |
