export const API_BASE = process.env.GATEWAY_URL;
export const WS_BASE  = process.env.GATEWAY_WS_URL;

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