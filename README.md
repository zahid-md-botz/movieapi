# ZAHID MOVIE API

- **Website / Brand:** ZAHID MOVIE API
- **API:** Movie Api
- **Developer:** Zahid dev
- **Footer:** POWERED BY ZAHID TECH
- **Support:** myweb615265@gmail.com

This repository runs as one Node.js service on Railway. It serves the website, API routes, admin/key-management UI, MovieBox request engine, and streaming endpoints. Cloudflare is not required.

## Deploy on Railway

Follow [`RAILWAY-DEPLOY.md`](RAILWAY-DEPLOY.md). The production API-key/quota/session database is SQLite stored on a Railway persistent volume mounted at `/app/.data`.

- Start command: `npm start`
- Runtime: Node.js 24
- Health check: `/api/v3/health`
- Railway config: [`railway.toml`](railway.toml)

Do not commit `.env`, `.data/`, SQLite files, or secrets. A passing health check confirms the Node service is running; MovieBox upstream search and real video playback must be checked separately after deployment.
