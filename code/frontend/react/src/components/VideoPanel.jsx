import React, { useState, useCallback } from "react";
import { Notice } from "./ui.jsx";
import { DropZone, ObuZone } from "./DropZone.jsx";
import { useServerStream } from "../modules/useServerStream.js";
import { useWasmModule }   from "../modules/useWasmModule.js";

/**
 * Component: main dashboard after login.
 *
 * Dependency Injection: videoRepo is passed in, not instantiated here.
 *
 * @param {{ token: string, username: string, onLogout: () => void, videoRepo: import("../api/VideoRepository").VideoRepository }} props
 */
export function VideoPanel({ token, username, onLogout, videoRepo }) {
  const [uploading,    setUploading]    = useState(false);
  const [obuUploading, setObuUploading] = useState(false);
  const [frame,        setFrame]        = useState(null);
  const [notice,       setNotice]       = useState({ msg: "", type: "" });
  const [videos,       setVideos]       = useState(null);

  const { data: streamData, error: streamError } = useServerStream(token);
  const { module: wasmModule, ready: wasmReady, loadError: wasmLoadError } = useWasmModule();

  // ── Standard upload ────────────────────────────────────────────────────────
  const upload = useCallback(async (file) => {
    setUploading(true);
    setFrame(null);
    setNotice({ msg: "", type: "" });
    try {
      const r    = await videoRepo.uploadBlob(token, file, file.name);
      const blob = await r.blob();
      setFrame(URL.createObjectURL(blob));
      setNotice({ msg: "Last frame extracted", type: "ok" });
    } catch (e) {
      setNotice({ msg: e.message, type: "error" });
    } finally {
      setUploading(false);
    }
  }, [token, videoRepo]);

  // ── OBU / WASM upload ──────────────────────────────────────────────────────
  const uploadObu = useCallback(async (file) => {
    if (!wasmReady) {
      setNotice({ msg: "WASM module not ready yet", type: "error" });
      return;
    }
    setObuUploading(true);
    setFrame(null);
    setNotice({ msg: "", type: "" });
    try {
      const M = wasmModule.current;

      const inputData = new Uint8Array(await file.arrayBuffer());
      M.FS.writeFile("/input.mp4", inputData);
      M.callMain(["/input.mp4"]);
      const outputData = M.FS.readFile("/packets.obu");

      const obuBlob  = new Blob([outputData], { type: "application/octet-stream" });
      const obuName  = file.name.replace(/\.[^.]+$/, ".obu");
      const r        = await videoRepo.uploadBlob(token, obuBlob, obuName);
      const blob     = await r.blob();

      setFrame(URL.createObjectURL(blob));
      setNotice({ msg: "OBU processed & last frame extracted", type: "ok" });
    } catch (e) {
      setNotice({ msg: e.message, type: "error" });
    } finally {
      setObuUploading(false);
    }
  }, [token, videoRepo, wasmReady, wasmModule]);

  const loadVideos = async () => {
    const data = await videoRepo.listVideos(token);
    setVideos(data);
  };

  return (
    <div style={{ width: 560 }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 28 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 22, fontFamily: "'DM Mono', monospace", color: "#eee" }}>Dashboard</h1>
          <p style={{ margin: "4px 0 0", color: "#555", fontSize: 13 }}>@{username}</p>
        </div>
        <button
          onClick={onLogout}
          style={{ background: "none", border: "1px solid #2a2a2a", borderRadius: 6, color: "#666", padding: "6px 14px", fontSize: 12, cursor: "pointer", letterSpacing: "0.06em" }}
        >
          Logout
        </button>
      </div>

      <Notice {...notice} />
      {streamError    && <div style={{ color: "#ff7a7a", fontSize: 12, marginBottom: 8 }}>Stream error: {streamError}</div>}
      {wasmLoadError  && <div style={{ color: "#ff7a7a", fontSize: 12, marginBottom: 8 }}>{wasmLoadError}</div>}
      {streamData     && <div style={{ fontSize: 12, color: "#555", marginBottom: 8 }}>Replicas: {JSON.stringify(streamData)}</div>}

      {/* Upload zones */}
      <DropZone
        inputId="fileinput"
        onFile={upload}
        uploading={uploading}
        label="Uploading..."
        sublabel="Drop video or click to browse"
      />
      <ObuZone
        onFile={uploadObu}
        uploading={obuUploading}
        disabled={!wasmReady}
      />

      {/* Last frame preview */}
      {frame && (
        <div style={{ marginBottom: 20 }}>
          <p style={{ margin: "0 0 8px", fontSize: 11, color: "#555", letterSpacing: "0.1em", textTransform: "uppercase" }}>Last Frame</p>
          <img src={frame} alt="Last frame" style={{ width: "100%", borderRadius: 8, border: "1px solid #1e1e1e", display: "block" }} />
        </div>
      )}

      {/* Video list */}
      <button
        onClick={loadVideos}
        style={{ background: "#111", border: "1px solid #222", borderRadius: 6, color: "#888", padding: "9px 18px", fontSize: 12, cursor: "pointer", letterSpacing: "0.06em" }}
      >
        Load video list
      </button>

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
}