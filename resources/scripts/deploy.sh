#!/usr/bin/env bash
set -euxo pipefail


if [ -z "${WAR_MANIFESTS+x}" ]; then
    echo "WAR_MANIFESTS is unset. Please provide a path to warnet manifests."
    exit 1
fi

# Function to check if warnet-rpc container is already running
check_warnet_rpc() {
    if kubectl get pods --all-namespaces | grep -q "bitcoindevproject/warnet-rpc"; then
        echo "warnet-rpc pod found"
        exit 1
    fi
}

# Deploy base configurations
kubectl apply -f "$WAR_MANIFESTS/namespace.yaml"
kubectl apply -f "$WAR_MANIFESTS/rbac-config.yaml"
kubectl apply -f "$WAR_MANIFESTS/warnet-rpc-service.yaml"

# Deploy rpc server
if [ -n "${WAR_DEV+x}" ]; then # Dev mode selector
    # Build image in local registry
    docker build -t warnet/dev -f "$WAR_RPC/Dockerfile_dev" "$WAR_RPC" --load
    if [ "$(kubectl config current-context)" = "docker-desktop" ]; then
        sed "s?/mnt/src?$(pwd)?g" "$WAR_MANIFESTS/warnet-rpc-statefulset-dev.yaml" | kubectl apply -f -
    else # assuming minikube
        minikube image load warnet/dev
        kubectl apply -f "$WAR_MANIFESTS/warnet-rpc-statefulset-dev.yaml"
    fi
else
    kubectl apply -f "$WAR_MANIFESTS/warnet-rpc-statefulset.yaml"
fi

kubectl config set-context --current --namespace=warnet

# Check for warnet-rpc container
check_warnet_rpc

until kubectl get pod rpc-0 --namespace=warnet; do
   echo "Waiting for server to find pod rpc-0..."
   sleep 4
done

echo "⏲️ This could take a minute or so."
kubectl wait --for=condition=Ready --timeout=2m pod rpc-0

echo Done...
