set shell := ["bash", "-uc"]
default_cpus := "4"
default_memory := "4000"

[private]
default:
    just --list

# Configure a minikube k8s cluster
minikube cpus=default_cpus memory=default_memory:
    WAR_RPC="./resources/images/rpc" WAR_CPU={{ cpus }} WAR_MEM={{ memory }} ./resources/scripts/setup_minikube.sh

# Deploy Warnet in dev mode
deploy:
    WAR_MANIFESTS="./resources/manifests" WAR_DEV=1 ./resources/scripts/deploy.sh

# Stop and teardown warnet
teardown:
    ./resources/scripts/stop.sh

# port forward
p:
    kubectl port-forward svc/rpc 9276:9276

# Quick start for minikube local dev
qs: minikube deploy p

registry := 'bitcoindevproject/bitcoin'
repo := 'bitcoin/bitcoin'
arches := 'amd64,arm64'
build-args := "--disable-tests --without-gui --disable-bench --disable-fuzz-binary --enable-suppress-external-warnings"
load := "load"

# Build docker image and optionally push to registry
build branch tag registry=registry repo=repo build-args=build-args action=load:
    warcli image build --registry={{registry}} --repo={{repo}} --branch={{branch}} --arches="{{arches}}" --tag={{tag}} --build-args="{{build-args}}" --action={{action}}

installlogging:
    ./resources/scripts/install_logging.sh

connectlogging:
    ./resources/scripts/connect_logging.sh

# Format and lint all files
lint:
    ruff format --check .
    ruff check .
