#!/usr/bin/env bash

# Run with e.g.:
# $ DOCKER_REGISTRY=bitcoindevproject/warnet-rpc TAG=0.1 LATEST=1 ./scripts/build-k8s-rpc.sh Dockerfile_rpc

# Fail on any step
set -ex

# Create a new builder to enable building multi-platform images
BUILDER_NAME="warnet-rpc-builder"
docker buildx create --name "$BUILDER_NAME" --use

# Read DOCKER_REGISTRY and TAG from the environment
: "${DOCKER_REGISTRY?Need to set DOCKER_REGISTRY}"
: "${TAG?Need to set TAG}"
: "${LATEST:=0}"

# Architectures for building
ARCHS="linux/amd64,linux/arm64"

# Read Dockerfile from the first argument
DOCKERFILE_PATH=$1
if [[ ! -f "$DOCKERFILE_PATH" ]]; then
  echo "Dockerfile does not exist at the specified path: $DOCKERFILE_PATH"
  exit 1
fi

# Determine the image tags
IMAGE_FULL_NAME="$DOCKER_REGISTRY:$TAG"
TAGS="--tag $IMAGE_FULL_NAME"

# If LATEST=1, add the latest tag
if [[ "$LATEST" -eq 1 ]]; then
    LATEST_TAG_IMAGE="$DOCKER_REGISTRY:latest"
    TAGS="$TAGS --tag $LATEST_TAG_IMAGE"
fi

# Use Buildx to build the image for the specified architectures and tag it accordingly
docker buildx build --platform "$ARCHS" \
    --file "$DOCKERFILE_PATH" \
    --progress=plain \
    $TAGS \
    . --push

docker buildx rm "$BUILDER_NAME"
