#!/bin/bash
set -e

helm repo add grafana https://grafana.github.io/helm-charts
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm upgrade --install --namespace warnet-logging --create-namespace --values "$PWD/manifests/loki_values.yaml" loki grafana/loki --version 5.47.2
helm upgrade --install --namespace warnet-logging promtail grafana/promtail
helm upgrade --install --namespace warnet-logging prometheus prometheus-community/kube-prometheus-stack --namespace warnet-logging --set grafana.enabled=false
helm upgrade --install --namespace warnet-logging loki-grafana manifests/grafana --values "$PWD/manifests/grafana_values.yaml"