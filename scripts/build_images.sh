#!/bin/bash

# Create a new builder to enable building multi-platform images
docker buildx create --use

# Image and Registry info
DOCKER_REGISTRY="bitcoindevproject/bitcoin-core"
BITCOIN_URL="https://bitcoincore.org/bin"
echo "DOCKER_REGISTRY=$DOCKER_REGISTRY"
echo "BITCOIN_URL=$BITCOIN_URL"

# Map internal architectures to the format used in the URLs
declare -A ARCH_MAP=(
    ["amd64"]="x86_64-linux-gnu"
    ["arm64"]="aarch64-linux-gnu"
    ["armhf"]="arm-linux-gnueabihf"
    # ["amd64-darwin"]="x86_64-apple-darwin"
    # ["arm64-darwin"]="arm64-apple-darwin"
)

# Tags and their supported architectures
declare -A VERSION_ARCH_MAP=(
    ["0.21.2"]="amd64 arm64 armhf"
    ["22.1"]="amd64 arm64 armhf"
    ["23.2"]="amd64 arm64 armhf"
    ["24.2"]="amd64 arm64 armhf"
    ["25.1"]="amd64 arm64 armhf"
)

if [ -d "src/templates" ]; then
  cd src/templates || exit 1
else
  echo "Directory src/templates does not exist. Please run this script from the project root."
  exit 1
fi

# Loop through each tag and its architectures to build and push
for VERSION in "${!VERSION_ARCH_MAP[@]}"; do
    IFS=' ' read -ra ARCHS <<< "${VERSION_ARCH_MAP[$VERSION]}"
    IMAGES_LIST=()  # Array to store images for manifest
    for DOCKER_ARCH in "${ARCHS[@]}"; do
        echo "VERSION=$VERSION"
        echo "DOCKER_ARCH=$DOCKER_ARCH"

        # Map the architecture to the URL format
        URL_ARCH=${ARCH_MAP[$DOCKER_ARCH]}
        echo "URL_ARCH=$URL_ARCH"

        IMAGE_TAG="$VERSION-$DOCKER_ARCH"
        IMAGE_FULL_NAME="$DOCKER_REGISTRY:$IMAGE_TAG"
        echo "IMAGE_FULL_NAME=$IMAGE_FULL_NAME"

        # Use Buildx to build the image for the specified architecture
        docker buildx build --platform linux/"$DOCKER_ARCH" \
            --provenance=false \
            --build-arg ARCH="$URL_ARCH" \
            --build-arg BITCOIN_VERSION="$VERSION" \
            --build-arg BITCOIN_URL="$BITCOIN_URL" \
            --tag "$IMAGE_FULL_NAME" \
            . --push

        IMAGES_LIST+=("$IMAGE_FULL_NAME")
    done

    # Create the manifest list for each version under the same repository
    MANIFEST_TAG="$DOCKER_REGISTRY:$VERSION"
    docker buildx imagetools create --tag "$MANIFEST_TAG" "${IMAGES_LIST[@]}"
done
