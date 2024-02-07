#!/bin/bash
set -e

POD_NAME=$(kubectl get pods --namespace warnet-logging -l "app.kubernetes.io/name=grafana,app.kubernetes.io/instance=loki-grafana" -o jsonpath="{.items[0].metadata.name}")

GRAFANA_PASSWORD=$(kubectl get secret --namespace warnet-logging loki-grafana -o jsonpath="{.data.admin-password}" | base64 --decode || true)

echo "Go to http://localhost:3000 and login with the username 'admin' and the password '${GRAFANA_PASSWORD}' to see your logs"

kubectl --namespace warnet-logging port-forward "${POD_NAME}" 3000