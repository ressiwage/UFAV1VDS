import React, { useState } from "react";
import { Input, Btn, Notice } from "./ui.jsx";
import { useAuth } from "../modules/useAuth.js";

/**
 * Component: authentication form (login / register).
 *
 * Dependency Injection: authRepo is passed in rather than instantiated here,
 * so the parent (App) controls which concrete repository is used.
 *
 * @param {{ authRepo: import("../api/AuthRepository").AuthRepository, onLogin: (token: string, username: string) => void }} props
 */
export function AuthPanel({ authRepo, onLogin }) {
  const { register, login } = useAuth(authRepo);

  const [mode,     setMode]     = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading,  setLoading]  = useState(false);
  const [notice,   setNotice]   = useState({ msg: "", type: "" });

  const submit = async () => {
    if (!username || !password) {
      setNotice({ msg: "Fill all fields", type: "error" });
      return;
    }
    setLoading(true);
    setNotice({ msg: "", type: "" });
    try {
      if (mode === "register") {
        await register(username, password);
        setNotice({ msg: "Registered! Now log in.", type: "ok" });
        setMode("login");
      } else {
        const t = await login(username, password);
        onLogin(t, username);
      }
    } catch (e) {
      setNotice({ msg: e.message, type: "error" });
    } finally {
      setLoading(false);
    }
  };

  const toggleMode = () => {
    setMode(m => (m === "login" ? "register" : "login"));
    setNotice({ msg: "", type: "" });
  };

  return (
    <div style={{ width: 360 }}>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ margin: 0, fontSize: 26, fontFamily: "'DM Mono', monospace", color: "#eee", letterSpacing: "-0.02em" }}>
          {mode === "login" ? "Sign in" : "Create account"}
        </h1>
        <p style={{ margin: "6px 0 0", color: "#555", fontSize: 13 }}>AV1 Video Uploader</p>
      </div>

      <Notice {...notice} />

      <Input label="Username" value={username} onChange={e => setUsername(e.target.value)} autoComplete="username" />
      <Input label="Password" type="password" value={password} onChange={e => setPassword(e.target.value)} onKeyDown={e => e.key === "Enter" && submit()} />

      <div style={{ marginBottom: 10 }}>
        <Btn variant="ghost" loading={loading} onClick={submit}>
          {mode === "login" ? "Sign in" : "Register"}
        </Btn>
      </div>

      <Btn variant="ghost" onClick={toggleMode}>
        {mode === "login" ? "No account? Register" : "Have an account? Sign in"}
      </Btn>
    </div>
  );
}