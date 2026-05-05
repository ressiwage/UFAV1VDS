import { useState } from "react";

/**
 * Module + Dependency Injection: auth state management.
 * Receives an AuthRepository instance instead of importing API details directly,
 * making it testable and decoupled from the network layer.
 *
 * @param {import("../api/AuthRepository").AuthRepository} authRepo
 */
export function useAuth(authRepo) {
  const [token, setToken] = useState(null);
  const [user,  setUser]  = useState(null);

  const register = (username, password) => authRepo.register(username, password);

  const login = async (username, password) => {
    const t = await authRepo.login(username, password);
    setToken(t);
    const u = await authRepo.getUser(t);
    setUser(u);
    return t;
  };

  const logout = () => { setToken(null); setUser(null); };

  return { token, user, register, login, logout };
}