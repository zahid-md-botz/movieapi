# ZAHID MOVIE API

- **Website / Brand:** ZAHID MOVIE API
- **API:** Movie Api
- **Developer:** Zahid dev
- **Footer:** POWERED BY ZAHID TECH
- **Support:** myweb615265@gmail.com

This repository keeps the existing Railway application as the source of truth for the website, API routes, admin/key-management UI, SQLite quotas and MovieBox request engine. A private localhost Python relay handles upstream media with Chrome-impersonating HTTP/2 and bounded streaming. The optional Cloudflare Worker in `cloudflare/worker.js` is the public edge gateway: it forwards requests and media responses as streams without buffering video.

## Deploy on Railway

Follow [`RAILWAY-DEPLOY.md`](RAILWAY-DEPLOY.md) first, then [`CLOUDFLARE-DEPLOY.md`](CLOUDFLARE-DEPLOY.md). The production API-key/quota/session database is SQLite stored on a Railway persistent volume mounted at `/app/.data`.

- Start command: `npm start`
- After the Worker is deployed, set the same `EDGE_SHARED_SECRET` in Railway and Cloudflare. The Railway origin then rejects direct public requests except its health check.
- Runtime: Node.js 24 + private Python media relay (Dockerfile)
- Health check: `/api/v3/health`
- Railway config: [`railway.toml`](railway.toml)

Do not commit `.env`, `.data/`, SQLite files, or secrets. A passing health check confirms the Node service is running; MovieBox upstream search and real video playback must be checked separately after deployment.
