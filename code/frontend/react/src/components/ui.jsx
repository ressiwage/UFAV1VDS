import React from "react";

// ─── Input ────────────────────────────────────────────────────────────────────
export const Input = ({ label, ...props }) => (
  <div style={{ marginBottom: 14 }}>
    <label style={{ display: "block", fontSize: 11, letterSpacing: "0.12em", textTransform: "uppercase", color: "#888", marginBottom: 5 }}>
      {label}
    </label>
    <input
      style={{ width: "100%", boxSizing: "border-box", background: "#0d0d0d", border: "1px solid #2a2a2a", borderRadius: 6, padding: "10px 14px", color: "#eee", fontSize: 14, outline: "none", transition: "border 0.2s" }}
      onFocus={e  => (e.target.style.border = "1px solid #5a5aff")}
      onBlur={e   => (e.target.style.border = "1px solid #2a2a2a")}
      {...props}
    />
  </div>
);

// ─── Button ───────────────────────────────────────────────────────────────────
export const Btn = ({ children, loading, variant = "primary", ...props }) => (
  <button
    style={{ width: "100%", padding: "11px 0", borderRadius: 6, fontSize: 13, fontWeight: 600, letterSpacing: "0.06em", cursor: loading ? "not-allowed" : "pointer", border: variant === "ghost" ? "1px solid #2a2a2a" : "none", background: variant === "ghost" ? "transparent" : loading ? "#3a3aaa" : "#5a5aff", color: variant === "ghost" ? "#888" : "#fff", transition: "background 0.2s", opacity: loading ? 0.7 : 1 }}
    disabled={loading}
    {...props}
  >
    {loading ? "..." : children}
  </button>
);

// ─── Notice ───────────────────────────────────────────────────────────────────
export const Notice = ({ msg, type }) =>
  msg ? (
    <div style={{ padding: "10px 14px", borderRadius: 6, fontSize: 13, marginBottom: 14, background: type === "error" ? "#2a0d0d" : "#0d1f0d", border: `1px solid ${type === "error" ? "#5a1a1a" : "#1a4a1a"}`, color: type === "error" ? "#ff7a7a" : "#7aff7a" }}>
      {msg}
    </div>
  ) : null;