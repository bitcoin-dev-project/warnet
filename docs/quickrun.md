# Quick run

Warnet runs a server which can be used to manage multiple networks. On docker
this runs locally, but on Kubernetes this runs as a `statefulSet` in the
cluster.

If the `$XDG_STATE_HOME` environment variable is set, the server will log to
a file `$XDG_STATE_HOME/warnet/warnet.log`, otherwise it will use `$HOME/.warnet/warnet.log`.

## Quick start via pip

You can install warnet via `pip` into your virtual environment with

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install warnet
```

Following installation `warcli` commands will operate natively on the Kubernetes cluster currently configured with `kubectl`.

Starting the Warnet server is as easy as:

```bash
# (optional) if using a local minikube cluster check that we have all required programs installed
warcli setup

# (optional) if using a local minikube cluster, set it up
warcli cluster minikube-setup

warcli cluster deploy
```

This also automatically configures port forwarding to the Server in the cluster.

To tear down the cluster:

```bash
warcli cluster teardown

# (optional) if using a local minikube cluster, remove the image
warcli cluster minikube-clean


