#!/usr/bin/env bash
set -euo pipefail
set +x
set +v

# Delete namespaces
kubectl delete namespace warnet --ignore-not-found
kubectl delete namespace warnet-logging --ignore-not-found

# Set the context to default namespace
kubectl config set-context --current --namespace=default

# Delete minikube, if it exists
if command -v minikube &> /dev/null; then
    minikube delete || true
fi
