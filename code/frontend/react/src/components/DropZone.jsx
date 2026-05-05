import React from "react";

/**
 * Component: drag-and-drop / click-to-browse upload zone.
 *
 * @param {{ onFile: (file: File) => void, uploading: boolean, inputId: string, label: string, sublabel: string, accentColor?: string, borderColor?: string }} props
 */
export function DropZone({
  onFile,
  uploading,
  inputId,
  label,
  sublabel,
  accentColor  = "#5a5aff",
  borderColor  = "#222",
}) {
  const [dragging, setDragging] = React.useState(false);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) onFile(file);
  };

  return (
    <div
      onDragOver={e => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => document.getElementById(inputId).click()}
      style={{ border: `2px dashed ${dragging ? accentColor : borderColor}`, borderRadius: 10, padding: "40px 20px", textAlign: "center", marginBottom: 14, transition: "border 0.2s, background 0.2s", background: dragging ? "#0d0d2a" : "#0a0a0a", cursor: "pointer", position: "relative" }}
    >
      <input
        id={inputId}
        type="file"
        accept="video/*,.av1,.ivf,.obu"
        style={{ display: "none" }}
        onChange={e => e.target.files[0] && onFile(e.target.files[0])}
      />
      {uploading ? (
        <div style={{ color: accentColor, fontSize: 13 }}>
          <div style={{ fontSize: 28, marginBottom: 8, animation: "spin 1s linear infinite" }}>⟳</div>
          {label}
        </div>
      ) : (
        <>
          <div style={{ fontSize: 32, marginBottom: 10, color: "#333" }}>↑</div>
          <div style={{ color: "#555", fontSize: 13 }}>{sublabel}</div>
        </>
      )}
    </div>
  );
}

/**
 * Component: secondary drop/click zone for OBU/WASM flow.
 */
export function ObuZone({ onFile, uploading, disabled }) {
  return (
    <div
      style={{ border: "2px dashed #1a2a1a", borderRadius: 10, padding: "20px", textAlign: "center", marginBottom: 20, background: "#0a0d0a", cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.5 : 1, transition: "opacity 0.3s" }}
      onClick={() => !disabled && document.getElementById("obuinput").click()}
      title={disabled ? "WASM module loading..." : ""}
    >
      <input
        id="obuinput"
        type="file"
        accept="video/*,.mp4,.mkv"
        style={{ display: "none" }}
        onChange={e => e.target.files[0] && onFile(e.target.files[0])}
      />
      {uploading ? (
        <div style={{ color: "#5aff5a", fontSize: 13 }}>
          <div style={{ fontSize: 28, marginBottom: 8, animation: "spin 1s linear infinite" }}>⟳</div>
          Encoding OBU via WASM...
        </div>
      ) : (
        <>
          <div style={{ fontSize: 22, marginBottom: 6, color: "#2a4a2a" }}>⬡</div>
          <div style={{ color: "#3a6a3a", fontSize: 13 }}>
            {disabled ? "Loading WASM..." : "Send separated OBU file — click to browse"}
          </div>
        </>
      )}
    </div>
  );
}