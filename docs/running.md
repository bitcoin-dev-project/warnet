# Running Warnet

Warnet runs a server which can be used to manage multiple networks. On docker
this runs locally, but on Kubernetes this runs as a `statefulSet` in the
cluster.

If the `$XDG_STATE_HOME` environment variable is set, the server will log to
a file `$XDG_STATE_HOME/warnet/warnet.log`, otherwise it will use `$HOME/.warnet/warnet.log`.

## Kubernetes

// TODO

### Install logging infrastructure

First make sure you have `helm` installed, then simply run the following script:

```bash
./scripts/install_logging.sh
```

To forward port to view Grafana dashboard:

```bash
./scripts/connect_logging.sh
```

## Kubernetes (e.g. minikube)

To start the server run:

```bash
warcli network start
```

Make sure the tanks are running with:

```bash
 warcli network status
```

Check if the edges of the nodes are connected with:

```bash
 warcli network connected
```

_Optional_ Check out the logs with:

```bash
warcli network logs -f
```

If that looks all good, give [scenarios](/docs/scenarios.md) a try.
