#!/bin/bash
set -e  # остановить выполнение при любой ошибке

# ================= НАСТРОЙКИ (меняйте под себя) =================
# Полные имена образов с тегами
IMAGES=(
    # "ghcr.io/ressiwage/frontend:latest"
    "ghcr.io/ressiwage/decoder-api:latest"
    # "ghcr.io/ressiwage/gateway:latest"
    # "ghcr.io/ressiwage/common-api:latest"
)

# Пути к Dockerfile (пустая строка → используется Dockerfile по умолчанию)
DOCKERFILES=(
    # ""                           # для frontend используем Dockerfile в контексте
    "decoder-api/Dockerfile"
    # "gateway/Dockerfile"
    # "common-api/Dockerfile"
)

# Контексты сборки (папки или текущая директория ".")
CONTEXTS=(
    # "frontend/react/"
    "."
    # "."
    # "."
)
# ================================================================

# Цикл по всем образам
for i in "${!IMAGES[@]}"; do
    image="${IMAGES[$i]}"
    dockerfile="${DOCKERFILES[$i]}"
    context="${CONTEXTS[$i]}"

    echo ">>> Building $image ..."
    if [ -n "$dockerfile" ]; then
        docker build --no-cache -t "$image" -f "$dockerfile" "$context"
    else
        docker build --no-cache -t "$image" "$context"
    fi

    echo ">>> Pushing $image ..."
    docker push "$image"
done

echo "✅ All builds and pushes completed."