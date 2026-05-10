#!/bin/sh
set -e

cat > /app/public/env-config.js << EOF
window.__ENV__ = {
  GATEWAY_URL: "${GATEWAY_URL}",
  GATEWAY_WS_URL: "${GATEWAY_WS_URL}"
};
EOF

echo "Runtime config:"
cat /app/public/env-config.js

exec npm run preview -- --host 0.0.0.0 --port 4173