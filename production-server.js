// Railway entrypoint: start the private Python HTTP/2 media relay, then Node API.
import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';

if (!process.env.ADMIN_SECRET || process.env.ADMIN_SECRET.length < 32) {
  throw new Error('ADMIN_SECRET is required and must be at least 32 characters');
}
if (!process.env.DATA_DIR || !process.env.DATA_DIR.startsWith('/')) {
  throw new Error('DATA_DIR must point to the Railway persistent volume, for example /app/.data');
}
process.env.NODE_ENV = 'production';
const relayPort = Number(process.env.MEDIA_RELAY_PORT || 8765);
const relayUrl = `http://127.0.0.1:${relayPort}/fetch`;
process.env.MEDIA_RELAY_URL = relayUrl;
const python = process.env.PYTHON_BIN || '/opt/venv/bin/python';
const relay = spawn(python, ['-m', 'uvicorn', 'media_transport.relay:app', '--host', '127.0.0.1', '--port', String(relayPort), '--no-access-log'], {
  cwd: process.cwd(), stdio: ['ignore', 'inherit', 'inherit'], env: process.env
});
relay.on('exit', code => {
  if (code !== null && !process.exitCode) {
    console.error(`[media-relay] exited unexpectedly (${code})`);
    process.exit(1);
  }
});

let ready = false;
for (let attempt = 0; attempt < 40; attempt++) {
  if (relay.exitCode !== null) throw new Error('Python media relay failed to start; see relay logs above');
  try {
    const response = await fetch(`http://127.0.0.1:${relayPort}/health`, { signal: AbortSignal.timeout(700) });
    if (response.ok) { ready = true; break; }
  } catch {}
  await delay(500);
}
if (!ready) {
  relay.kill('SIGTERM');
  throw new Error('Python media relay did not become healthy within 20 seconds');
}
console.log('[media-relay] Chrome-impersonating HTTP/2 transport ready (8 concurrent streams)');
await import('./local-server.js');

const shutdown = () => { relay.kill('SIGTERM'); process.exit(0); };
process.once('SIGTERM', shutdown);
process.once('SIGINT', shutdown);
