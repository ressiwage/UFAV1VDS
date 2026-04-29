import { useState, useCallback, useEffect, useRef } from "react";

const API = "http://192.168.64.103:8000";


// ─── Auth ─────────────────────────────────────────────────────────────────────
const useAuth = () => {
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);

  const register = async (username, password) => {
    const r = await fetch(`${API}/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!r.ok) throw new Error((await r.json()).detail);
    return true;
  };

  const login = async (username, password) => {
    const r = await fetch(`${API}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!r.ok) throw new Error((await r.json()).detail);
    const { access_token: t } = await r.json();
    setToken(t);
    const ur = await fetch(`${API}/user`, { headers: { Authorization: `Bearer ${t}` } });
    setUser(await ur.json());
    return t;
  };

  const logout = () => { setToken(null); setUser(null); };
  return { token, user, register, login, logout };
};

// ─── UI primitives ────────────────────────────────────────────────────────────
const Input = ({ label, ...props }) => (
  <div style={{ marginBottom: 14 }}>
    <label style={{ display: "block", fontSize: 11, letterSpacing: "0.12em", textTransform: "uppercase", color: "#888", marginBottom: 5 }}>{label}</label>
    <input
      style={{ width: "100%", boxSizing: "border-box", background: "#0d0d0d", border: "1px solid #2a2a2a", borderRadius: 6, padding: "10px 14px", color: "#eee", fontSize: 14, outline: "none", transition: "border 0.2s" }}
      onFocus={e => e.target.style.border = "1px solid #5a5aff"}
      onBlur={e => e.target.style.border = "1px solid #2a2a2a"}
      {...props}
    />
  </div>
);

const Btn = ({ children, loading, variant = "primary", ...props }) => (
  <button
    style={{ width: "100%", padding: "11px 0", borderRadius: 6, fontSize: 13, fontWeight: 600, letterSpacing: "0.06em", cursor: loading ? "not-allowed" : "pointer", border: variant === "ghost" ? "1px solid #2a2a2a" : "none", background: variant === "ghost" ? "transparent" : loading ? "#3a3aaa" : "#5a5aff", color: variant === "ghost" ? "#888" : "#fff", transition: "background 0.2s", opacity: loading ? 0.7 : 1 }}
    disabled={loading}
    {...props}
  >
    {loading ? "..." : children}
  </button>
);

const Notice = ({ msg, type }) => msg ? (
  <div style={{ padding: "10px 14px", borderRadius: 6, fontSize: 13, marginBottom: 14, background: type === "error" ? "#2a0d0d" : "#0d1f0d", border: `1px solid ${type === "error" ? "#5a1a1a" : "#1a4a1a"}`, color: type === "error" ? "#ff7a7a" : "#7aff7a" }}>{msg}</div>
) : null;

// ─── Auth panel ───────────────────────────────────────────────────────────────
const AuthPanel = ({ onLogin }) => {
  const { register, login } = useAuth();
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState({ msg: "", type: "" });

  const submit = async () => {
    if (!username || !password) return setNotice({ msg: "Fill all fields", type: "error" });
    setLoading(true); setNotice({ msg: "", type: "" });
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
    } finally { setLoading(false); }
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
      <Btn variant="ghost" onClick={() => { setMode(mode === "login" ? "register" : "login"); setNotice({ msg: "", type: "" }); }}>
        {mode === "login" ? "No account? Register" : "Have an account? Sign in"}
      </Btn>
    </div>
  );
};

// ─── Shared upload logic ───────────────────────────────────────────────────────
// Получить presigned URL и загрузить blob
async function uploadBlob(token, blob, filename) {
  const neccessary_ram = 12345;
  const fd = new FormData();
  fd.append("file", blob, filename);
  const startTime = performance.now();
  const r = await fetch(`${API}/upload?neccessary_ram=${neccessary_ram}`, { method: "POST", body: fd });
  if (!r.ok) { const d = await r.json(); throw new Error(d.detail); }
  const endTime = performance.now();
  const totalMs = (endTime - startTime).toFixed(2);
  console.log(`[Upload] Total time (request → image response): ${totalMs} ms`);
  return r;
}

// ─── Video panel ──────────────────────────────────────────────────────────────
const VideoPanel = ({ token, username, onLogout }) => {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [frame, setFrame] = useState(null);
  const [notice, setNotice] = useState({ msg: "", type: "" });
  const [videos, setVideos] = useState(null);


  // Обычная загрузка (mp4/mkv → сервер сразу)
  const upload = async (file) => {
    setUploading(true); setFrame(null); setNotice({ msg: "", type: "" });
    try {
      const r = await uploadBlob(token, file, file.name);
      const blob = await r.blob();
      setFrame(URL.createObjectURL(blob));
      setNotice({ msg: "Last frame extracted", type: "ok" });
    } catch (e) {
      setNotice({ msg: e.message, type: "error" });
    } finally { setUploading(false); }
  };

  

  const loadVideos = async () => {
    const r = await fetch(`${API}/videos`, { headers: { Authorization: `Bearer ${token}` } });
    setVideos(await r.json());
  };

  const onDrop = useCallback((e) => {
    e.preventDefault(); setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) upload(file);
  }, [token]);

  return (
    <div style={{ width: 560 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 28 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 22, fontFamily: "'DM Mono', monospace", color: "#eee" }}>Dashboard</h1>
          <p style={{ margin: "4px 0 0", color: "#555", fontSize: 13 }}>@{username}</p>
        </div>
        <button onClick={onLogout} style={{ background: "none", border: "1px solid #2a2a2a", borderRadius: 6, color: "#666", padding: "6px 14px", fontSize: 12, cursor: "pointer", letterSpacing: "0.06em" }}>Logout</button>
      </div>

      <Notice {...notice} />

      {/* ── Drop zone (обычный upload) ── */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        style={{ border: `2px dashed ${dragging ? "#5a5aff" : "#222"}`, borderRadius: 10, padding: "40px 20px", textAlign: "center", marginBottom: 14, transition: "border 0.2s, background 0.2s", background: dragging ? "#0d0d2a" : "#0a0a0a", cursor: "pointer", position: "relative" }}
        onClick={() => document.getElementById("fileinput").click()}
      >
        <input id="fileinput" type="file" accept="video/*,.av1,.ivf,.obu" style={{ display: "none" }}
          onChange={e => e.target.files[0] && upload(e.target.files[0])} />
        {uploading ? (
          <div style={{ color: "#5a5aff", fontSize: 13 }}>
            <div style={{ fontSize: 28, marginBottom: 8, animation: "spin 1s linear infinite" }}>⟳</div>
            Uploading...
          </div>
        ) : (
          <>
            <div style={{ fontSize: 32, marginBottom: 10, color: "#333" }}>↑</div>
            <div style={{ color: "#555", fontSize: 13 }}>Drop video or click to browse</div>
          </>
        )}
      </div>


      {/* Last frame */}
      {frame && (
        <div style={{ marginBottom: 20 }}>
          <p style={{ margin: "0 0 8px", fontSize: 11, color: "#555", letterSpacing: "0.1em", textTransform: "uppercase" }}>Last Frame</p>
          <img src={frame} alt="Last frame" style={{ width: "100%", borderRadius: 8, border: "1px solid #1e1e1e", display: "block" }} />
        </div>
      )}

      <button onClick={loadVideos} style={{ background: "#111", border: "1px solid #222", borderRadius: 6, color: "#888", padding: "9px 18px", fontSize: 12, cursor: "pointer", letterSpacing: "0.06em" }}>Load video list</button>

      {videos && (
        <div style={{ marginTop: 16 }}>
          {Object.entries(videos).map(([arch, vids]) => (
            <div key={arch} style={{ marginBottom: 12 }}>
              <p style={{ margin: "0 0 6px", fontSize: 11, color: "#555", letterSpacing: "0.1em", textTransform: "uppercase" }}>{arch}</p>
              {vids.map(v => (
                <div key={v} style={{ padding: "8px 12px", background: "#0d0d0d", border: "1px solid #1e1e1e", borderRadius: 5, fontSize: 13, color: "#ccc", marginBottom: 4 }}>{v}</div>
              ))}
            </div>
          ))}
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
};

// ─── App ──────────────────────────────────────────────────────────────────────
export default function App() {
  const [session, setSession] = useState(null);
  return (
    <div style={{ minHeight: "100vh", background: "#080808", display: "flex", alignItems: "center", justifyContent: "center", padding: 24, fontFamily: "'DM Mono', 'Courier New', monospace" }}>
      <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&display=swap" rel="stylesheet" />
      {!session
        ? <AuthPanel onLogin={(token, username) => setSession({ token, username })} />
        : <VideoPanel token={session.token} username={session.username} onLogout={() => setSession(null)} />
      }
    </div>
  );
}