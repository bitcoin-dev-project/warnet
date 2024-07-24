set shell := ["bash", "-uc"]

[private]
default:
    just --list

cluster:
    kubectl apply -f src/warnet/templates/rpc/namespace.yaml
    kubectl apply -f src/warnet/templates/rpc/rbac-config.yaml
    kubectl apply -f src/warnet/templates/rpc/warnet-rpc-service.yaml
    kubectl apply -f src/warnet/templates/rpc/warnet-rpc-statefulset.yaml

# Setup and start the RPC in dev mode with minikube
start:
    #!/usr/bin/env bash
    set -euxo pipefail

    # Function to check if minikube is running
    check_minikube() {
        minikube status | grep -q "Running" && echo "Minikube is already running" || minikube start --mount --mount-string="$PWD:/mnt/src"
    }

    # Function to check if warnet-rpc container is already running
    check_warnet_rpc() {
        if kubectl get pods --all-namespaces | grep -q "bitcoindevproject/warnet-rpc"; then
            echo "warnet-rpc already running in minikube"
            exit 1
        fi
    }

    # Check minikube status
    check_minikube

    # Build image in local registry and load into minikube
    docker build -t warnet/dev -f src/warnet/templates/rpc/Dockerfile_rpc_dev src/warnet/templates/rpc --load
    minikube image load warnet/dev

    # Setup k8s
    kubectl apply -f src/warnet/templates/rpc/namespace.yaml
    kubectl apply -f src/warnet/templates/rpc/rbac-config.yaml
    kubectl apply -f src/warnet/templates/rpc/warnet-rpc-service.yaml
    kubectl apply -f src/warnet/templates/rpc/warnet-rpc-statefulset-dev.yaml
    kubectl config set-context --current --namespace=warnet

    # Check for warnet-rpc container
    check_warnet_rpc

    until kubectl get pod rpc-0 --namespace=warnet; do
       echo "Waiting for server to find pod rpc-0..."
       sleep 4
    done

    echo "⏲️ This could take a minute or so."
    kubectl wait --for=condition=Ready --timeout=2m pod rpc-0

    echo Done...

# Stop the RPC in dev mode with minikube
stop:
    #!/usr/bin/env bash
    set -euxo pipefail

    kubectl delete namespace warnet
    kubectl delete namespace warnet-logging
    kubectl config set-context --current --namespace=default

    minikube image rm warnet/dev

# Setup and start the RPC in dev mode with Docker Desktop
startd:
    docker build -t warnet/dev -f src/warnet/templates/rpc/Dockerfile_rpc_dev src/warnet/templates/rpc --load
    kubectl apply -f src/warnet/templates/rpc/namespace.yaml
    kubectl apply -f src/warnet/templates/rpc/rbac-config.yaml
    kubectl apply -f src/warnet/templates/rpc/warnet-rpc-service.yaml
    sed 's?/mnt/src?'`PWD`'?g' src/warnet/templates/rpc/warnet-rpc-statefulset-dev.yaml | kubectl apply -f -
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
    ./src/warnet/templates/k8s/install_logging.sh

connectlogging:
    ./src/warnet/templates/k8s/connect_logging.sh

# Format and lint all files
lint:
    ruff format --check .
    ruff check .
