#!/usr/bin/env bash
set -euxo pipefail

if [ $# -eq 0 ]; then
    echo "Please provide a path as an argument."
    exit 1
fi
RPC_PATH="$1"

docker build -t warnet/dev -f "$RPC_PATH/Dockerfile_rpc_dev src/warnet/templates/rpc" --load
kubectl apply -f "$RPC_PATH/namespace.yaml"
kubectl apply -f "$RPC_PATH/rbac-config.yaml"
kubectl apply -f "$RPC_PATH/warnet-rpc-service.yaml"
sed "s?/mnt/src?$(pwd)?g" "$RPC_PATH/warnet-rpc-statefulset-dev.yaml" | kubectl apply -f -
kubectl config set-context --current --namespace=warnet

echo waiting for rpc to come online
kubectl wait --for=condition=Ready --timeout=2m pod rpc-0

echo Done...
