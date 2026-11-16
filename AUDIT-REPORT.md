# Source audit and delivery report

## Scope and evidence

The original Movie API archive has 134 entries, including directories. The second
upload was byte-identical. The later provider archive has three files: the
JavaScript engine, JavaScript stream proxy, and the publisher's resource notice.
Neither archive supplied the Python `provider/engine.py` referenced by the old
bootstrap scripts.

All original archive entries were inventoried and read for integrity/hash checks;
text files were scanned for imports/configuration and JSON was parsed. The runtime
entry points, Python service, engine, routing, key/short-link store interactions,
media transport, manga scraper and test contracts received targeted inspection.
This is not a claim of a formal security audit or manual line-by-line review of
every HTML/sample-data byte. `SOURCE-INVENTORY.json` records per-file handling.
Private SQLite databases and local cache contents were not displayed or migrated.

## Changes and reasons

1. Added `python-origin/engine.py`: owner-approved Python adaptation of the supplied
   JavaScript engine's real requests, signing, metadata, stream and caption logic.
   It is an adaptation, not recovery of the missing original Python implementation.
2. Added Python catalog processing for the existing public catalog routes. The
   production Worker now delegates that processing to Railway after its key/quota
   gate. Existing response envelopes remain at the compatibility gateway.
3. Ported the existing manga selectors and response fields to Python with
   BeautifulSoup. Removed the runtime reliance on the third-party CORS proxy.
   Manga ZIPs are built on temporary disk with size limits, not in unbounded RAM.
   Unknown image hosts and missing pages fail explicitly.
4. Added Python 3.13 Dockerfiles for both documented build contexts and Railway
   configurations. Replaced runtime source-bundle installation with build-time
   dependency installation. `local.py` imports the shipped engine directly.
5. Moved the real curl transport into the self-contained Python directory. A small
   compatibility import remains at its previous location.
6. Set `ENGINE_RELAY_URL` to an explicit placeholder. No Railway URL was invented.
   Preserved Cloudflare account, KV, Durable Object bindings and migration names.
7. Added If-Range forwarding across the Worker hop; rejected empty byte ranges;
   bounded the incoming authenticated request-body read.
8. Trailer metadata preserves its nested shape while supported trailer URLs are
   signed gateway URLs that use Railway's media relay. Unknown CDN hosts are not
   silently treated as supported.
9. Added adapter, backend catalog and gateway/trailer contract tests. Removed test
   dependence on a nonexistent provider ZIP.
10. Corrected one stale test assertion only after reproducing its failure against
    the untouched original source. It expected exposed upstream status, while the
    existing error-sanitization contract intentionally hides it.
11. Kept `public/` pages byte-for-byte unchanged. Exact duplicate root assets are
    excluded from the delivery ZIP; legacy local file serving now uses `public/`.
    Sample JSON remains documentation only, never a live fallback.
12. Added a resolved pnpm lockfile and documented the actual environment variables.
    No existing database was replaced or migrated.

## Intentional boundaries / compatibility caveats

* Cloudflare still handles authentication, quotas, playback authorization, public
  link construction and manifest link rewriting. These are gateway/storage
  functions; the content provider and media origin are Python on Railway.
* The old standalone Node development server is preserved, not the deployment
  target. It does not represent the new production Python path.
* The adapter does not copy the supplied JavaScript's fabricated forwarding-IP
  headers or restriction-override headers. It does not bypass provider restrictions.
* Membership-restricted streams are not presented as free streams.
* Missing native signing configuration produces an error rather than mock data.
* Direct manga fetching may be rejected where the old third-party CORS relay
  worked. That needs provider-approved resolution, not a claim that the port is
  already live-verified.
* The supplied optional `tg-storage` module is absent and was never part of the
  original Python deployment. No replacement was fabricated. Existing Cloudflare
  short-link storage is retained instead.
* Existing retired endpoints remain retired; no unrelated UI redesign was made.
* Existing static documentation/sample content can contain historical provider
  examples. It is not proof of today's provider availability.

## Validation results

| Check | Result |
|---|---|
| Python runtime | Python 3.13.11 available |
| Python direct dependencies | Installed successfully at the specified versions |
| Python compile check | Passed |
| Python unit/contract tests | **20 passed** |
| JavaScript tests | **36 passed** |
| Real Python process startup from Node test | Passed; health and unauthorized/invalid request checks passed |
| Wrangler production build dry-run | Passed; static assets and bindings recognized |
| Syntax checks on modified JS entry points | Passed |
| Live homepage | Returned 18 sections and 190 subject entries during probe |
| Live detail metadata | Returned a title, poster URL, description and trailer metadata |
| Live search | Initial web query returned zero matches; **not verified**. Native fallback added and still requires configured signing key/live acceptance |
| Live movie ranges/playback | **Not verified**; source lookup failed in live probe |
| Trailer playback / poster-image fetch | **Not verified**, only metadata observed |
| Live manga and archive bytes | **Not verified**; parsing contract tested using fixtures |
| Live Railway ↔ Cloudflare deployment | **Not tested**, no user URL/credentials/deployment supplied |
| Docker build | **Not executed**; Docker execution is unavailable in this environment |

The FastAPI TestClient emitted a deprecation warning about its httpx integration;
tests passed. This warning is not a live runtime failure.

## Remaining requirements before production acceptance

Configure the user's Railway URL and real secrets, build the Docker image, deploy
to the existing accounts, and run every acceptance check in DEPLOYMENT-GUIDE.md.
Native MovieBox operations need `MOVIEBOX_SIGNING_KEY_B64` from the authorized
provider configuration. No such secret was configured during this delivery.
Verify search relevance, anime details, caption/audio fields, trailer playback,
actual stream/download ranges, HLS/DASH segments, image loading and manga downloads.
Successful local tests and metadata calls do **not** establish those behaviors.

The original uploaded archives are retained separately and unchanged. Runtime
`.data/`, `.wrangler/`, installed dependencies and generated build output are
excluded from the deliverable; their omission does not delete production data.
