# Running Warnet

Warnet runs a server which can be used to manage multiple networks. On docker
this runs locally, but on Kubernetes this runs as a `statefulSet` in the
cluster.

If the `$XDG_STATE_HOME` environment variable is set, the server will log to
a file `$XDG_STATE_HOME/warnet/warnet.log`, otherwise it will use `$HOME/.warnet/warnet.log`.

## Kubernetes

Deploy the resources in `src/warnet/templates/`, this sets up the correct permissions on the cluster (`rbac-config.yaml`) and deploys the warnet RPC server as a service + statefulset.

This can be done with from inside the `src/warnet/templates/` directory by running:

```bash
kubectl apply -f '*.yaml'
```

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
./src/warnet/templates/k8s/install_logging.sh
```

To forward port to view Grafana dashboard:

```bash
./src/warnet/templates/k8s/connect_logging.sh
```

## Kubernetes (e.g. minikube)

To start the server run:

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
