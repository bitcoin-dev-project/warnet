[private]
default:
    just --list

# (k)ubernetes (d)ev
kd:
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

    # Create the statefulset
    kubectl apply -f src/templates/rpc/rbac-config.yaml -f src/templates/rpc/warnet-rpc-service.yaml -f src/templates/rpc/warnet-rpc-statefulset-dev.yaml
    echo Done...

# (k)ubernetes (d)ev (d)own
kdd:
    #!/usr/bin/env bash
    set -euxo pipefail
    echo Tearing down kubernetes dev mode

    # Check we're in home dir
    if [ ! -f "$PWD/pyproject.toml" ]; then \
      echo "Error: must run from project root." >&2; exit 1; \
    fi

    # Stop statefulset
    kubectl delete -f src/templates/rpc/warnet-rpc-statefulset.yaml

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
    sed 's?/mnt/src?'`PWD`'?g' src/templates/rpc/warnet-rpc-statefulset-dev.yaml | kubectl apply -f src/templates/rpc/rbac-config.yaml -f src/templates/rpc/warnet-rpc-service.yaml -f -

    # Create the statefulset
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

    # Replace mount path with local directory
    kubectl delete -f src/templates/rpc/warnet-rpc-statefulset.yaml
    # Create the statefulset
    echo Done...
