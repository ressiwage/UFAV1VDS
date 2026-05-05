import { useEffect, useRef, useState } from "react";
import { WS_BASE } from "../api/config.js";

/**
 * Module: encapsulates WebSocket lifecycle for server-sent notifications.
 *
 * @param {string|null} token  — JWT; pass null to stay disconnected
 * @returns {{ data: object|null, error: string|null }}
 */
export function useServerStream(token) {
  const [data,  setData]  = useState(null);
  const [error, setError] = useState(null);
  const wsRef = useRef(null);

  useEffect(() => {
    if (!token) return;

    const ws = new WebSocket(
      `${WS_BASE}/ws/client_notification?token=${encodeURIComponent(token)}`
    );
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === "error")  { setError(msg.detail); ws.close(); }
      else  setData(msg);
      console.log(msg);
    };
    ws.onerror = () => setError("Connection error");
    ws.onclose = (event) => { if (event.code === 4001) setError("Unauthorized"); };

    return () => ws.close();
  }, [token]);

  return { data, error };
}