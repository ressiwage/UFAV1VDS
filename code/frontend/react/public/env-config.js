// Этот файл используется только локально (npm run dev)
// В продакшене перезаписывается docker-entrypoint.sh
window.__ENV__ = {
  GATEWAY_URL: "http://localhost:7995",
  GATEWAY_WS_URL: "ws://localhost:7995/ws/replica"
};