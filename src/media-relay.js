// Production media requests are sent to the private localhost curl-cffi relay.
// Local development retains the Node fetch transport unless MEDIA_RELAY_URL is set.
import { fetchMedia as fetchNodeMedia } from './tickets.js';

const RELAY_URL = process.env.MEDIA_RELAY_URL || '';

export async function fetchMedia(url, headers, range = null, method = 'GET', fallbackFetch = globalThis.fetch) {
    if (!RELAY_URL) return fetchNodeMedia(url, headers, range, method, fallbackFetch);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(new Error('Private media relay timed out before opening the upstream stream')), 160000);
    try {
        // Clear the connection timeout as soon as response headers arrive; the
        // same signal must not cut off a legitimate long-running video stream.
        return await fetch(RELAY_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(range ? { Range: range } : {})
            },
            body: JSON.stringify({ url, headers, method }),
            signal: controller.signal
        });
    } finally {
        clearTimeout(timer);
    }
}
