#!/bin/bash
set -e  # остановить выполнение при любой ошибке

# ================= НАСТРОЙКИ (меняйте под себя) =================
# Полные имена образов с тегами
IMAGES=(
    "ghcr.io/ressiwage/frontend:latest"
    "ghcr.io/ressiwage/decoder-api:latest"
    "ghcr.io/ressiwage/gateway:latest"
    "ghcr.io/ressiwage/common-api:latest"
)



# Цикл по всем образам
for i in "${!IMAGES[@]}"; do
    image="${IMAGES[$i]}"
    docker pull "$image"
done

echo "✅ All builds and pushes completed."