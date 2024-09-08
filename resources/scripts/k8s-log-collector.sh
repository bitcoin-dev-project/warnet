#!/bin/bash

# Set variables
NAMESPACE=${1:-default}
LOG_DIR="./k8s-logs"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Collect logs using stern (includes logs from terminated pods)
echo "Collecting stern logs..."
stern "(tank|commander).*" --namespace="$NAMESPACE" --output default --since 1h --no-follow > "$LOG_DIR/${TIMESTAMP}_stern_logs"

# Collect descriptions of all resources
echo "Collecting resource descriptions..."
kubectl describe all --namespace="$NAMESPACE" > "$LOG_DIR/${TIMESTAMP}_resource_descriptions.txt"

# Collect events
echo "Collecting events..."
kubectl get events --namespace="$NAMESPACE" --sort-by='.metadata.creationTimestamp' > "$LOG_DIR/${TIMESTAMP}_events.txt"

echo "Log collection complete. Logs saved in $LOG_DIR"
