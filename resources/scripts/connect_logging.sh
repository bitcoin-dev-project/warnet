#!/bin/bash
# NO `set -e` here so an error does not exit the script

POD_NAME=$(kubectl get pods --namespace warnet-logging -l "app.kubernetes.io/name=grafana,app.kubernetes.io/instance=loki-grafana" -o jsonpath="{.items[0].metadata.name}")

echo "Go to http://localhost:3000"
echo "Grafana pod name: ${POD_NAME}"

while true; do
  echo "Attempting to start Grafana port forwarding"
  kubectl --namespace warnet-logging port-forward "${POD_NAME}" 3000 2>&1
  echo "Grafana port forwarding exited with status: $?"
  sleep 5
done;

echo "warnet-logging port-forward exited"