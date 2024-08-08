#!/usr/bin/env bash
set -euo pipefail
set +x
set +v

if [ -z "${WAR_RPC+x}" ]; then
    echo "WAR_RPC is unset. Please provide a path to warnet RPC images."
    exit 1
fi

# Check minikube status
minikube delete

# Prepare minikube start command
MINIKUBE_CMD="minikube start --driver=docker --container-runtime=containerd --mount --mount-string=\"$PWD:/mnt/src\""

# Check for WAR_CPU and add to command if set
if [ -n "${WAR_CPU:-}" ]; then
    MINIKUBE_CMD="$MINIKUBE_CMD --cpus=$WAR_CPU"
fi

# Check for WAR_MEM and add to command if set
if [ -n "${WAR_MEM:-}" ]; then
    MINIKUBE_CMD="$MINIKUBE_CMD --memory=${WAR_MEM}m"
fi

# Start minikube with the constructed command
eval "$MINIKUBE_CMD"

# Build image in local registry and load into minikube
docker build -t warnet/dev -f "$WAR_RPC/Dockerfile_dev" "$WAR_RPC" --load
minikube image load warnet/dev

echo Done...
