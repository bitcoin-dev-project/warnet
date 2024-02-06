#!/usr/bin/env bash

# Run from the src/templates dir with e.g.:
#
# $ DOCKER_REGISTRY=bitcoindevproject/demo TAG=26.0 ../../scripts/build-k8s-rpc.sh Dockerfile_rpc_alpine


BUILDER_NAME="warnet-bitcoind-builder"
# Cleanup function to remove the Docker builder
cleanup() {
  echo "Removing builder..."
  docker buildx rm "$BUILDER_NAME" || echo "Failed to remove builder $BUILDER_NAME"
}

# Set up trap to call cleanup function on EXIT signal
trap cleanup EXIT SIGINT SIGTERM

set -ex

# Create a new builder to enable building multi-platform images
docker buildx create --name "$BUILDER_NAME" --use

# Read DOCKER_REGISTRY from the environment
: "${DOCKER_REGISTRY?Need to set DOCKER_REGISTRY}"
: "${TAG?Need to set TAG}"

# Architectures for building
ARCHS="linux/amd64,linux/arm64"

# Read Dockerfile from the first argument
DOCKERFILE_PATH=$1
if [[ ! -f "$DOCKERFILE_PATH" ]]; then
  echo "Dockerfile does not exist at the specified path: $DOCKERFILE_PATH"
  exit 1
fi

# Loop through each architecture to build and push
IMAGE_FULL_NAME="$DOCKER_REGISTRY:$TAG"

# Use Buildx to build the image for the specified architecture
docker buildx build --platform "$ARCHS" \
    --file "$DOCKERFILE_PATH" \
    --progress=plain \
    --tag "$IMAGE_FULL_NAME" \
    --build-arg REPO="$REPO" \
    --build-arg BRANCH="$BRANCH" \
    --build-arg BUILD_ARGS="$BUILD_ARGS" \
    . --push
