[private]
default:
    just --list

# Setup and start the RPC in dev mode
start:
    #!/usr/bin/env bash
    set -euxo pipefail
    echo Running k8s in dev mode

    # Check we're in home dir
    if [ ! -f "$PWD/pyproject.toml" ]; then \
      echo "Error: must run from project root." >&2; exit 1; \
    fi

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

# Stop the RPC in dev mode
stop:
    #!/usr/bin/env bash
    set -euxo pipefail
    echo Tearing down kubernetes dev mode

    # Check we're in home dir
    if [ ! -f "$PWD/pyproject.toml" ]; then \
      echo "Error: must run from project root." >&2; exit 1; \
    fi

    # Stop statefulset
    kubectl delete -f src/templates/rpc/warnet-rpc-statefulset-dev.yaml
    kubectl delete -f src/templates/rpc/warnet-rpc-service.yaml
    kubectl delete -f src/templates/rpc/rbac-config.yaml
    kubectl delete -f src/templates/rpc/namespace.yaml
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

# (d)ocker (d)esktop (k)ubernetes (d)ev
ddkd:
    #!/usr/bin/env bash
    set -euxo pipefail
    echo Running k8s in dev mode

    # Check we're in home dir
    if [ ! -f "$PWD/pyproject.toml" ]; then \
      echo "Error: must run from project root." >&2; exit 1; \
    fi

    # Replace mount path with local directory

    kubectl apply -f src/templates/rpc/namespace.yaml
    kubectl apply -f src/templates/rpc/rbac-config.yaml
    kubectl apply -f src/templates/rpc/warnet-rpc-service.yaml
    kubectl apply -f src/templates/rpc/warnet-rpc-statefulset-dev.yaml
    sed 's?/mnt/src?'`PWD`'?g' src/templates/rpc/warnet-rpc-statefulset-dev.yaml | kubectl apply -f -
    kubectl config set-context --current --namespace=warnet

    echo waiting for rpc to come online
    kubectl wait --for=condition=Ready --timeout=2m pod rpc-0

    echo Done...

# (d)ocker (d)esktop (k)ubernetes (d)ev (d)own
ddkdd:
    #!/usr/bin/env bash
    set -euxo pipefail
    echo Tearing down kubernetes dev mode

    # Check we're in home dir
    if [ ! -f "$PWD/pyproject.toml" ]; then \
      echo "Error: must run from project root." >&2; exit 1; \
    fi

    # Deleting all resources
    kubectl delete -f src/templates/rpc/warnet-rpc-statefulset-dev.yaml
    kubectl delete -f src/templates/rpc/warnet-rpc-service.yaml
    kubectl delete -f src/templates/rpc/rbac-config.yaml
    kubectl delete -f src/templates/rpc/namespace.yaml
    kubectl config set-context --current --namespace=default

    echo Done...

# port forward
p:
    kubectl port-forward svc/rpc 9276:9276
