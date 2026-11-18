// Production media requests are sent to the private localhost curl-cffi relay.
// Local development retains the Node fetch transport unless MEDIA_RELAY_URL is set.
import { fetchMedia as fetchNodeMedia } from './tickets.js';

const RELAY_URL = process.env.MEDIA_RELAY_URL || '';

export async function fetchMedia(url, headers, range = null, method = 'GET', fallbackFetch = globalThis.fetch, ifRange = null) {
    if (!RELAY_URL) return fetchNodeMedia(url, headers, range, method, fallbackFetch);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(new Error('Private media relay timed out before opening the upstream stream')), 160000);
    try {
        // Clear the connection timeout as soon as response headers arrive; the
        // same signal must not cut off a legitimate long-running video stream.
        const response = await fetch(RELAY_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(range ? { Range: range } : {}),
                ...(ifRange ? { 'If-Range': ifRange } : {})
            },
            body: JSON.stringify({ url, headers, method }),
            signal: controller.signal
        });
        // If the private relay cannot connect to the CDN, give the Node
        // transport one chance. This helps deployments where the relay's
        // HTTP/2 path is blocked but normal HTTPS is available.
        if (response.status >= 500 || [421, 425, 426, 429].includes(response.status)) {
            await response.arrayBuffer().catch(() => {});
            return fetchNodeMedia(url, headers, range, method, fallbackFetch);
        }
        return response;
    } finally {
        clearTimeout(timer);
    }
}
