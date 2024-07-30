#!/bin/bash
set -e

POD_NAME=$(kubectl get pods --namespace warnet-logging -l "app.kubernetes.io/name=grafana,app.kubernetes.io/instance=loki-grafana" -o jsonpath="{.items[0].metadata.name}")

echo "Go to http://localhost:3000 and login with the username 'admin' and the password 'password' to see your logs"

kubectl --namespace warnet-logging port-forward "${POD_NAME}" 3000