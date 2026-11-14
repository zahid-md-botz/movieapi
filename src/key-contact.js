const SUPPORT_EMAIL = 'myweb615265@gmail.com';
const emailLink = (subject, message) => `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(message)}`;
export const upgradeContact = reason => emailLink(
    'Movie Api key support',
    `Hi Zahid dev, I need help with my Movie Api key${reason ? ' (' + reason + ')' : ''}. Please help me review or upgrade my access.`
);
export const keyContact = (key, reason) => !key || key === 'zahidmovieapi'
    ? { contact: '/request-key', contactAction: 'request_key', contactLabel: 'Request your own key',
        hint: 'Request your own API key for dedicated limits.' }
    : { contact: upgradeContact(reason), contactAction: 'upgrade', contactLabel: 'Email support',
        hint: 'For limit increases, renewals or key upgrades, email support.' };
export const requestContact = (request, id) => emailLink(
    `Movie Api key request ${id}`,
    `New Movie Api key request\nReference: ${id}\nName: ${request.name}\nEmail: ${request.email || '—'}\nPhone: ${request.phone || '—'}\nWebsite: ${request.website || '—'}\nUse case: ${request.useCase}`
);
