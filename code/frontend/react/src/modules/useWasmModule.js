import { useEffect, useRef, useState } from "react";

/**
 * Module: manages loading and caching of the Emscripten WASM module.
 * Uses window.__wasmModule* as a cross-mount singleton so the script is
 * only injected once even across hot-reloads.
 *
 * @returns {{ module: React.MutableRefObject, ready: boolean, loadError: string|null }}
 */
export function useWasmModule() {
  const moduleRef  = useRef(null);
  const [ready,     setReady]     = useState(false);
  const [loadError, setLoadError] = useState(null);

  useEffect(() => {
    if (window.__wasmModuleReady) {
      moduleRef.current = window.__wasmModuleInstance;
      setReady(true);
      return;
    }

    window.Module = {
      locateFile: (path) => (path.endsWith(".wasm") ? "/output.wasm" : path),
      onRuntimeInitialized() {
        window.__wasmModuleInstance = window.Module;
        window.__wasmModuleReady    = true;
        moduleRef.current           = window.Module;
        setReady(true);
      },
    };

    const script    = document.createElement("script");
    script.src      = "/output.js";
    script.onerror  = () => setLoadError("Failed to load WASM module");
    document.body.appendChild(script);
    // Script is intentionally not removed — the Module runtime depends on it.
  }, []);

  return { module: moduleRef, ready, loadError };
}