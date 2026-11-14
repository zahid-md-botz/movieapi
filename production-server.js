// Railway production entrypoint. API keys, quotas and playback sessions use
// SQLite on the Railway persistent volume mounted at /app/.data.
if (!process.env.ADMIN_SECRET || process.env.ADMIN_SECRET.length < 32) {
  throw new Error('ADMIN_SECRET is required and must be at least 32 characters');
}
if (!process.env.DATA_DIR || !process.env.DATA_DIR.startsWith('/')) {
  throw new Error('DATA_DIR must point to the Railway persistent volume, for example /app/.data');
}
process.env.NODE_ENV = 'production';
await import('./local-server.js');
