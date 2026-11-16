/** Resolve the public API origin without leaking the private Railway origin. */
export function publicOrigin(req) {
    const configured = String(process.env.PUBLIC_BASE_URL || '').trim();
    if (configured) {
        try {
            const url = new URL(configured);
            if (url.protocol === 'https:' && !url.username && !url.password &&
                url.pathname === '/' && !url.search && !url.hash) return url.origin;
        } catch {}
        throw new Error('PUBLIC_BASE_URL must be an HTTPS origin, for example https://movieapi.example.workers.dev');
    }
    const forwardedHost = String(req.headers['x-forwarded-host'] || '').split(',')[0].trim();
    const host = /^[a-z0-9.-]+(?::[0-9]{1,5})?$/i.test(forwardedHost) ? forwardedHost : req.get('host');
    const forwardedProto = String(req.headers['x-forwarded-proto'] || '').split(',')[0].trim().toLowerCase();
    const protocol = forwardedProto === 'https' ? 'https' : (req.secure ? 'https' : 'http');
    if (!host || /[^a-z0-9.\-:\[\]]/i.test(host)) throw new Error('Unable to determine public API host');
    return `${protocol}://${host}`;
}
