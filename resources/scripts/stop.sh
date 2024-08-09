#!/usr/bin/env bash
set -euxo pipefail

# Delete namespaces
kubectl delete namespace warnet --ignore-not-found
kubectl delete namespace warnet-logging --ignore-not-found

# Set the context to default namespace
kubectl config set-context --current --namespace=default

# Delete minikube, if it exists
minikube delete || true
