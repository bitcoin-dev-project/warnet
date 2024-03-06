set shell := ["bash", "-uc"]

[private]
default:
    just --list

# Setup and start the RPC in dev mode with minikube
start:
    #!/usr/bin/env bash
    set -euxo pipefail

    # Mount local source dir
    minikube mount $PWD:/mnt/src > /tmp/minikube_mount.log 2>&1 &

    # Capture the PID of the minikube mount command
    MINIKUBE_MOUNT_PID=$!

    # Save the PID to a file for later use
    echo $MINIKUBE_MOUNT_PID > /tmp/minikube_mount.pid

    # Setup k8s
    kubectl apply -f src/templates/rpc/namespace.yaml
    kubectl apply -f src/templates/rpc/rbac-config.yaml
    kubectl apply -f src/templates/rpc/warnet-rpc-service.yaml
    kubectl apply -f src/templates/rpc/warnet-rpc-statefulset-dev.yaml
    kubectl config set-context --current --namespace=warnet

    echo waiting for rpc to come online
    sleep 2
    kubectl wait --for=condition=Ready --timeout=2m pod rpc-0

    echo Done...

# Stop the RPC in dev mode with minikube
stop:
    #!/usr/bin/env bash
    set -euxo pipefail

    kubectl delete namespace warnet
    kubectl delete namespace warnet-logging
    kubectl config set-context --current --namespace=default

    # Fetch job ID of `minikube mount $PWD:/mnt/src` from saved PID file
    if [ -f /tmp/minikube_mount.pid ]; then
       MINIKUBE_MOUNT_PID=$(cat /tmp/minikube_mount.pid)
       # Stop the background job using its PID
       kill -SIGINT $MINIKUBE_MOUNT_PID
       # Optionally, remove the PID file
       rm /tmp/minikube_mount.pid
    else
        echo "PID file not found. Minikube mount process may not have been started."
    fi

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
action := "load"

# Build docker image and optionally push to registry
build branch tag registry=registry repo=repo action=action build-args=build-args:
    warcli image build --registry={{registry}} --repo={{repo}} --branch={{branch}} --arches="{{arches}}" --tag={{tag}} --build-args="{{build-args}}" --action={{action}}

installlogging:
    ./src/templates/k8s/install_logging.sh

connectlogging:
    ./src/templates/k8s/connect_logging.sh