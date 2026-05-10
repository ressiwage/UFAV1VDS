const env = window.__ENV__ || {};

var IPS = {
  'msk-1-vm-zcps': '194.87.131.81',
  '7624415-eg826155.twc1.net': '72.56.39.104'
}

export const API_BASE = `http://${IPS[env.HOSTNAME]}:7995`;
export const WS_BASE  = `ws://${IPS[env.HOSTNAME]}:7995/ws/replica`;

console.log("AB WB", API_BASE, WS_BASE)

/**
 * Thin wrapper around fetch that throws on non-2xx with the server's detail message.
 */
export async function apiFetch(url, options = {}) {
  const r = await fetch(url, options);
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.detail ?? `HTTP ${r.status}`);
  }
  return r;
}