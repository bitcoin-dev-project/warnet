#!/usr/bin/env bash

# Fail on any step
set -ex

# Create a new builder to enable building multi-platform images
docker buildx create --use

# Read DOCKER_REGISTRY from the environment
: "${DOCKER_REGISTRY?Need to set DOCKER_REGISTRY}"

# Architectures for building
ARCHS=("amd64" "arm64" "armhf")

# Read Dockerfile from the first argument
DOCKERFILE_PATH=$1
if [[ ! -f "$DOCKERFILE_PATH" ]]; then
  echo "Dockerfile does not exist at the specified path: $DOCKERFILE_PATH"
  exit 1
fi

# Loop through each architecture to build and push
IMAGES_LIST=()  # Array to store images for manifest
for DOCKER_ARCH in "${ARCHS[@]}"; do
    IMAGE_TAG="$DOCKER_ARCH"
    IMAGE_FULL_NAME="$DOCKER_REGISTRY:$IMAGE_TAG"
  
    # Use Buildx to build the image for the specified architecture
    docker buildx build --platform linux/"$DOCKER_ARCH" \
        --file "$DOCKERFILE_PATH" \
        --tag "$IMAGE_FULL_NAME" \
        src/templates --push  # set build context to src/templates

    IMAGES_LIST+=("$IMAGE_FULL_NAME")
done

# Create the manifest list under the same repository
MANIFEST_TAG="$DOCKER_REGISTRY:latest"
docker buildx imagetools create --tag "$MANIFEST_TAG" "${IMAGES_LIST[@]}"

