import { API_BASE, apiFetch } from "./config.js";

/**
 * Repository pattern: all server calls related to authentication live here.
 * Nothing outside this module needs to know about endpoint paths or
 * request shapes for auth.
 */
export class AuthRepository {
  async register(username, password) {
    await apiFetch(`${API_BASE}/register`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ username, password }),
    });
  }

  async login(username, password) {
    const r    = await apiFetch(`${API_BASE}/login`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ username, password }),
    });
    const { access_token } = await r.json();
    return access_token;
  }

  async getUser(token) {
    const r = await apiFetch(`${API_BASE}/user`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return r.json();
  }
}