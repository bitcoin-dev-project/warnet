#!/bin/bash
set -e

kubectl apply -f src/templates/rpc/namespace.yaml
kubectl apply -f src/templates/rpc/rbac-config.yaml
kubectl apply -f src/templates/rpc/warnet-rpc-service.yaml
kubectl apply -f src/templates/rpc/warnet-rpc-statefulset.yaml