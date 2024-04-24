set shell := ["bash", "-uc"]

[private]
default:
    just --list

cluster:
    kubectl apply -f src/templates/rpc/namespace.yaml
    kubectl apply -f src/templates/rpc/rbac-config.yaml
    kubectl apply -f src/templates/rpc/warnet-rpc-service.yaml
    kubectl apply -f src/templates/rpc/warnet-rpc-statefulset.yaml

# Setup and start the RPC in dev mode with minikube
start:
    #!/usr/bin/env bash
    set -euxo pipefail

    if ! minikube delete; then
        echo "Detected a fresh minikube environment."
    fi

    minikube start --mount --mount-string="$PWD:/mnt/src"

    # Setup k8s
    kubectl apply -f src/templates/rpc/namespace.yaml
    kubectl apply -f src/templates/rpc/rbac-config.yaml
    kubectl apply -f src/templates/rpc/warnet-rpc-service.yaml
    kubectl apply -f src/templates/rpc/warnet-rpc-statefulset-dev.yaml
    kubectl config set-context --current --namespace=warnet

    until kubectl get pod rpc-0 --namespace=warnet; do
       echo "Waiting for server to find pod rpc-0..."
       sleep 4
    done

    kubectl wait --for=condition=Ready --timeout=2m pod rpc-0

    echo Done...

# Stop the RPC in dev mode with minikube
stop:
    #!/usr/bin/env bash
    set -euxo pipefail

    kubectl delete namespace warnet
    kubectl delete namespace warnet-logging
    kubectl config set-context --current --namespace=default

# Setup and start the RPC in dev mode with Docker Desktop
startd:
    kubectl apply -f src/templates/rpc/namespace.yaml
    kubectl apply -f src/templates/rpc/rbac-config.yaml
    kubectl apply -f src/templates/rpc/warnet-rpc-service.yaml
    sed 's?/mnt/src?'`PWD`'?g' src/templates/rpc/warnet-rpc-statefulset-dev.yaml | kubectl apply -f -
    kubectl config set-context --current --namespace=warnet

    echo waiting for rpc to come online
    kubectl wait --for=condition=Ready --timeout=2m pod rpc-0

    echo Done...

# Stop the RPC in dev mode with Docker Desktop
stopd:
    # Delete all resources
    kubectl delete namespace warnet
    kubectl delete namespace warnet-logging
    kubectl config set-context --current --namespace=default

    echo Done...

# port forward
p:
    kubectl port-forward svc/rpc 9276:9276

registry := 'bitcoindevproject/bitcoin'
repo := 'bitcoin/bitcoin'
arches := 'amd64,arm64'
build-args := "--disable-tests --without-gui --disable-bench --disable-fuzz-binary --enable-suppress-external-warnings"
load := "load"

# Build docker image and optionally push to registry
build branch tag registry=registry repo=repo build-args=build-args action=load:
    warcli image build --registry={{registry}} --repo={{repo}} --branch={{branch}} --arches="{{arches}}" --tag={{tag}} --build-args="{{build-args}}" --action={{action}}

installlogging:
    ./src/templates/k8s/install_logging.sh

connectlogging:
    ./src/templates/k8s/connect_logging.sh