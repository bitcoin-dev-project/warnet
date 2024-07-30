# Quick run

## Installation

Either install warnet via pip, or clone the source and install:

### via pip

You can install warnet via `pip` into a virtual environment with

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install warnet
```

### via cloned source

You can install warnet from source into a virtual environment with

```bash
git clone https://github.com/bitcoin-dev-project/warnet.git
cd warnet
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Running

> [!TIP]
> When developing locally add the `--dev` flag to `warcli cluster deploy` to enable dev mode with hot-reloading server.

### Using minikube

To run a local cluster using minikube:

```bash
warcli cluster setup-minikube

warcli cluster deploy
```

### Other cluster types

If not using minikube (e.g. using Docker Desktop or a managed cluster), `warcli` commands will operate natively on the current Kubernetes context, so you can simply run:

```bash
warcli cluster deploy
```

...to deploy warnet to your cluster.

`warcli deploy` also automatically configures port forwarding to the Server in the cluster.

## Stopping

To tear down the cluster:

```bash
warcli cluster teardown
```

## Log location

If the `$XDG_STATE_HOME` environment variable is set, the server will log to a file `$XDG_STATE_HOME/warnet/warnet.log`, otherwise it will use `$HOME/.warnet/warnet.log`.
