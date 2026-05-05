import { API_BASE, apiFetch } from "./config.js";

const NECESSARY_RAM = 12345;

/**
 * Repository pattern: all server calls related to video upload & listing.
 */
export class VideoRepository {
  /**
   * Fetches a presigned upload URL from the server, then POSTs the blob to it.
   * Returns the raw Response so the caller can stream the body (e.g. last-frame image).
   *
   * @param {string}  token
   * @param {Blob}    blob
   * @param {string}  filename
   * @returns {Promise<Response>}
   */
  async uploadBlob(token, blob, filename) {
    const startTime = performance.now();

    const presigned = await apiFetch(
      `${API_BASE}/upload?neccessary_ram=${NECESSARY_RAM}`,
      { method: "GET", headers: { auth: `Bearer ${token}` } }
    );
    const { url } = await presigned.json();

    const fd = new FormData();
    fd.append("file", blob, filename);

    const r = await apiFetch(url, { method: "POST", body: fd });

    console.log(
      `[Upload] Total time (request → image response): ${(performance.now() - startTime).toFixed(2)} ms`
    );

    return r;
  }

  /**
   * @param {string} token
   * @returns {Promise<Record<string, string[]>>}
   */
  async listVideos(token) {
    const r = await apiFetch(`${API_BASE}/videos`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return r.json();
  }
}