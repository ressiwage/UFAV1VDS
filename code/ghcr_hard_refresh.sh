#!/bin/bash
set -e

REGISTRY="ghcr.io/ressiwage"
STACK="myapp"

SERVICES=(
  "frontend:frontend/react/:frontend"
  "common-api:.:common-api"
  "gateway:.:gateway"
  "decoder-api:.:decoder-api"
)

for entry in "${SERVICES[@]}"; do
  IFS=":" read -r service context dockerfile <<< "$entry"
  IMAGE="$REGISTRY/$service:latest"

  echo "==> Building $IMAGE"
  docker build -t "$IMAGE" -f "$dockerfile/Dockerfile" "$context"

  echo "==> Pushing $IMAGE"
  docker push "$IMAGE"

  echo "==> Updating $STACK_$service"
  docker service update --force --image "$IMAGE" "${STACK}_${service}"

  echo "==> Done: $service"
  echo ""
done

echo "All services updated."