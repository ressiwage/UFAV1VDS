// const env = window.__ENV__ || {};


export const API_BASE = 'http://gateway:7995';
export const WS_BASE  = 'ws://gateway:7995/ws/url';

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