# Running Warnet

Warnet runs a server which can be used to manage multiple networks. On docker
this runs locally, but on Kubernetes this runs as a `statefulSet` in the
cluster.

If the `$XDG_STATE_HOME` environment variable is set, the server will log to
a file `$XDG_STATE_HOME/warnet/warnet.log`, otherwise it will use `$HOME/.warnet/warnet.log`.

## Kubernetes

Deploy the resources in `src/templates/`, this sets up a Kubernetes cluster, apply correct permissions on the cluster (`rbac-config.yaml`), and deploys the warnet RPC server as a service + statefulset.

### Using Justfile

The `justfile` in this project defines various tasks for managing the Kubernetes deployment workflow. Using this option requires that you have a local installation of [just](https://github.com/casey/just). So go ahead and install it if you do not have it already installed on your machine.

Follow the usage example below to run a task from the `justfile`.

`just start` - setup and start the RPC with minikube

<details>
    <summary>start details</summary>

    ```
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
    kubectl apply -f src/templates/rpc/warnet-rpc-statefulset.yaml
    kubectl config set-context --current --namespace=warnet

    echo waiting for rpc to come online
    sleep 2
    kubectl wait --for=condition=Ready --timeout=2m pod rpc-0

    echo Done...
    ```

</details>

`just stop` - stop the RPC in dev mode with minikube

<details>
    <summary>stop details</summary>

    ```
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
    ```

</details>

`just startd` - setup and start the RPC in dev mode with Docker Desktop

<details>
    <summary>startd details</summary>

    ```
    kubectl apply -f src/templates/rpc/namespace.yaml
    kubectl apply -f src/templates/rpc/rbac-config.yaml
    kubectl apply -f src/templates/rpc/warnet-rpc-service.yaml
    sed 's?/mnt/src?'`PWD`'?g' src/templates/rpc/warnet-rpc-statefulset-dev.yaml | kubectl apply -f -
    kubectl config set-context --current --namespace=warnet

    echo waiting for rpc to come online
    kubectl wait --for=condition=Ready --timeout=2m pod rpc-0

    echo Done...
    ```

</details>

`just stopd` - stop the RPC in dev mode with Docker Desktop

<details>
    <summary>stopd details</summary>

    ```
    # Delete all resources
    kubectl delete namespace warnet
    kubectl delete namespace warnet-logging
    kubectl config set-context --current --namespace=default

    echo Done...
    ```

</details>

`just p` - forwards port from local into the cluster

<details>
    <summary>port forward details</summary>

    ```
    kubectl port-forward svc/rpc 9276:9276
    ```

</details>

### Running the commands directly

You can setup the cluster following the steps below, if you do not wish to use the `justfile` option above.

```bash
# Creates a Kubernetes namespace for the RPC
kubectl apply -f src/templates/rpc/namespace.yaml

# Applies Role-Based Access Control (RBAC) configuration for the RPC
kubectl apply -f src/templates/rpc/rbac-config.yaml

# Deploys a service to expose the RPC
kubectl apply -f src/templates/rpc/warnet-rpc-service.yaml

# Deploys a statefulset for the RPC to manage stateful applications
kubectl apply -f src/templates/rpc/warnet-rpc-statefulset.yaml

```

### Setup and Start RPC in Development Mode with Minikube

The commands below sets up and starts the RPC service in development mode using Minikube. The steps are as follows:

```bash
# Mounts the local source directory to the Minikube virtual machine, allowing the RPC service to access code and files from the local development environment.
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

# Wait for the RPC pod to become ready, ensuring that the service is fully operational before proceeding.
sleep 2
kubectl wait --for=condition=Ready --timeout=2m pod rpc-0

```

### Stop RPC in Development Mode with Minikube

Follow the steps below to stop the RPC service running in development mode using Minikube:

```bash
# Deletes the Kubernetes namespaces 'warnet' and 'warnet-logging', which contain the resources associated with the RPC service and its logging, respectively.
kubectl delete namespace warnet
kubectl delete namespace warnet-logging

# Sets the current Kubernetes context to the default namespace, ensuring that subsequent Kubernetes commands operate within this namespace.
kubectl config set-context --current --namespace=default

# Fetch job ID of `minikube mount $PWD:/mnt/src` from saved PID file
if [ -f /tmp/minikube_mount.pid ]; then
    MINIKUBE_MOUNT_PID=$(cat /tmp/minikube_mount.pid)
    # Stop the background job using its PID
    kill -SIGINT $MINIKUBE_MOUNT_PID
    # Optionally, removes the PID file
    rm /tmp/minikube_mount.pid
else
    echo "PID file not found. Minikube mount process may not have been started."
fi

```

### Setup and Start RPC in Development Mode with Docker Desktop

Follow the steps below to setup and start the RPC service in development mode using Docker Desktop:

```bash
# Apply Kubernetes manifests for the RPC service, including namespace, RBAC configuration, and servce definition.
kubectl apply -f src/templates/rpc/namespace.yaml
kubectl apply -f src/templates/rpc/rbac-config.yaml
kubectl apply -f src/templates/rpc/warnet-rpc-service.yaml

#Applies the StatefulSet manifest for the RPC service, substituting the local source directory path ($PWD) in the manifest using sed command.
sed 's?/mnt/src?'`PWD`'?g' src/templates/rpc/warnet-rpc-statefulset-dev.yaml | kubectl apply -f -

# Sets the current Kubernetes context to the 'waarnet' namespace, ensuring that subsequent Kubernetes command operate within this namespace
kubectl config set-context --current --namespace=warnet

# Waits for the RPC service to become ready within a timeout period of 2 minutes
kubectl wait --for=condition=Ready --timeout=2m pod rpc-0

```

### Stop RPC in Development Mode with Docker Desktop

The steps below stops the RPC service running in development mode with Docker Desktop:

```bash
# Deletes the 'warnet' and 'warnet-logging' namespaces, which contain resources related to the RPC service and logging.
kubectl delete namespace warnet
kubectl delete namespace warnet-logging

# Sets the current Kubernetes context to the 'default' namespace.
kubectl config set-context --current --namespace=default

```

### Port Forwarding

Once the RPC server comes up we need to forward the RPC port from the cluster.
This can be done with:

```bash
kubectl port-forward svc/rpc 9276:9276
```

This allows you to communicate with the RPC server using `warcli`. Developers
should check the [developer notes](developer-notes.md) to see how to
update the RPC server when developing on Kubernetes.

Currently, while `warcli network down` will bring down the pods, the RPC server needs manual deletion.
This can be done using:

```bash
kubectl delete statefulset
```

### Install logging infrastructure

First make sure you have `helm` installed, then simply run the following script:

```bash
./src/templates/k8s/install_logging.sh
```

To forward port to view Grafana dashbaord:

```bash
./src/templates/k8s/connect_logging.sh
```

## Compose

To start the server in the foreground simply run:

```bash
warnet
```

### Running large networks

When running a large number of containers on a single host machine (i.e. with the Docker interface), the system may run out of various resources.
We recommend setting the following values in /etc/sysctl.conf:

```sh
# Increase ARP cache thresholds to improve network performance under high load
# gc_thresh1 - Adjust to higher threshold to retain more ARP entries and avoid cache overflow
net.ipv4.neigh.default.gc_thresh1 = 80000

# gc_thresh2 - Set the soft threshold for garbage collection to initiate ARP entry clean up
net.ipv4.neigh.default.gc_thresh2 = 90000

# gc_thresh3 - Set the hard threshold beyond which the system will start to drop ARP entries
net.ipv4.neigh.default.gc_thresh3 = 100000

# Increase inotify watchers limit to allow more files to be monitored for changes
# This is beneficial for applications like file sync services, IDEs or web development servers
fs.inotify.max_user_watches = 100000

# Increase the max number of inotify instances to prevent "Too many open files" error
# This is useful for users or processes that need to monitor a large number of file systems or directories simultaneously.
fs.inotify.max_user_instances = 100000

```

Apply the settings by either restarting the host, or without restarting using:

```sh
sudo sysctl -p
```

In addition to these settings, you may need to increase the maximum number of permitted open files for the user running the docker daemon (usually root) in /etc/security/limits.conf.
This change is often not necessary though so we recommend trying your network without it first.

The following command will apply it to a single shell session, and not persist it.
Use as root before launching docker.

```sh
# Increase the number of open files allowed per process to 4096
ulimit -n 4096
```

If you are running docker as a service via systemd you can apply it by adding the following to the service file and restarting the service:

```sh
# Add the following under the [Service] section of the unit file
LimitNOFILE=4096
```

Reload the systemd configuration and restart the unit afterwards:

```
sudo systemctl daemon-reload
sudo systemctl restart docker
```

On Ubuntu this file is located at `/lib/systemd/system/docker.service` but you can find it using `sudo systemctl status docker`.
