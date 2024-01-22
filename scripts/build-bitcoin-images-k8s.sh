#!/usr/bin/env bash

# Create a new builder to enable building multi-platform images
docker buildx create --use

# Image and Registry info
DOCKER_REGISTRY="bitcoindevproject/k8s-bitcoin-core"
REPO="bitcoin/bitcoin"
BUILD_ARGS="--disable-tests --with-incompatible-bdb --without-gui --disable-bench --disable-fuzz-binary --enable-suppress-external-warnings --without-miniupnpc --without-natpmp"
echo "DOCKER_REGISTRY=${DOCKER_REGISTRY}"
echo "REPO=${REPO}"

# Tags and their supported architectures
declare -A VERSION_ARCH_MAP=(
    ["23.2"]="amd64 arm64 armhf"
    ["24.2"]="amd64 arm64 armhf"
    ["25.1"]="amd64 arm64 armhf"
    ["26.0"]="amd64 arm64 armhf"
)

if [[ -d "src/templates" ]]; then
  cd src/templates || exit 1
else
  echo "Directory src/templates does not exist. Please run this script from the project root."
  exit 1
fi

# Loop through each tag and its architectures to build and push
for VERSION in "${!VERSION_ARCH_MAP[@]}"; do
    IFS=' ' read -ra ARCHS <<< "${VERSION_ARCH_MAP[${VERSION}]}"
    IMAGES_LIST=()  # Array to store images for manifest
    for DOCKER_ARCH in "${ARCHS[@]}"; do
        echo "BRANCH=v${VERSION}"
        echo "DOCKER_ARCH=${DOCKER_ARCH}"

        IMAGE_TAG="${VERSION}-${DOCKER_ARCH}"
        IMAGE_FULL_NAME="${DOCKER_REGISTRY}:${IMAGE_TAG}"
        echo "IMAGE_FULL_NAME=${IMAGE_FULL_NAME}"

        # Use Buildx to build the image for the specified architecture
        docker buildx build --platform linux/"${DOCKER_ARCH}" \
            --provenance=false \
            --build-arg REPO="${REPO}" \
            --build-arg BRANCH="v${VERSION}" \
            --build-arg BUILD_ARGS="${BUILD_ARGS}" \
            --tag "${IMAGE_FULL_NAME}" \
            --file Dockerfile_k8 \
            . --push

        IMAGES_LIST+=("${IMAGE_FULL_NAME}")
    done

    # Create the manifest list for each version under the same repository
    MANIFEST_TAG="${DOCKER_REGISTRY}:${VERSION}"
    docker buildx imagetools create --tag "${MANIFEST_TAG}" "${IMAGES_LIST[@]}"
done
