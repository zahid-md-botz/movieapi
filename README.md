# ZAHID MOVIE API

- **Website / Brand:** ZAHID MOVIE API
- **API:** Movie Api
- **Developer:** Zahid dev
- **Footer:** POWERED BY ZAHID TECH
- **Support:** myweb615265@gmail.com

This repository runs as one Railway service plus an optional Cloudflare media edge. Node.js serves the website, API routes, admin/key-management UI and MovieBox request engine. The Cloudflare Worker fetches signed media from the CDN so public playback does not depend on Railway's outbound CDN route.

## Deploy on Railway

Follow [`RAILWAY-DEPLOY.md`](RAILWAY-DEPLOY.md) and [`CLOUDFLARE-DEPLOY.md`](CLOUDFLARE-DEPLOY.md). The production API-key/quota/session database is SQLite stored on a Railway persistent volume mounted at `/app/.data`.

- Start command: `npm start`
- Runtime: Node.js 24 + private Python media relay (Dockerfile)
- Health check: `/api/v3/health`
- Railway config: [`railway.toml`](railway.toml)

Do not commit `.env`, `.data/`, SQLite files, or secrets. A passing health check confirms the Node service is running; MovieBox upstream search and real video playback must be checked separately after deployment.
