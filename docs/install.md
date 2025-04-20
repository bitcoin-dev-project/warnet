# Installing Warnet

Warnet runs on Kubernetes (k8s) and requires the Helm Kubernetes package manager in order to run the network.
The Kubernetes cluster can be run locally via minikube, Docker Desktop, k3d or similar, or remotely via Googles GKE, Digital Ocean, etc..
The utilities `kubectl` and `helm` must be installed and found on $PATH to administer the network.

## Install Warnet

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

## Dependencies

The [`helm`](https://helm.sh/) and [`kubectl`](https://kubernetes.io/docs/reference/kubectl/) utilities are required for all configurations to talk to and administrate your cluster.
These can be installed using your operating system's package manager, a third party package manager like [homebrew](https://brew.sh/), or as binaries directly into a python virtual environment created for warnet, by following the steps in [Use warnet to install dependencies](#use-warnet-to-install-dependencies).

If you are using a cloud-based cluster, these are the only tools needed.

### Use warnet to install dependencies

```bash
# Ensure the virtual environment is active
source .venv/bin/activate

# Run `warnet setup` to be guided through downloading binaries into the
# python virtual environment
warnet setup
```

### Running Warnet Locally

If the number of nodes you are running can run on one machine (think a dozen or so) then Warnet can happily run on a local Kubernetes.
Two supported local Kubernetes implementations are Minikube and Docker Desktop.

#### Docker Desktop

[Docker desktop](https://www.docker.com/products/docker-desktop/) includes the docker engine itself and has an option to enable Kubernetes.
Install it and enable Kubernetes in the option menu to start a cluster.

#### Minikube

Minikube requires a backend to run on with the supported backend being Docker.

[Install Docker](https://docs.docker.com/engine/install/) first, and then proceed to [Install Minkube](https://minikube.sigs.k8s.io/docs/start/).

After installing Minikube don't forget to start it with:

```shell
minikube start
```

Minikube has a [guide](https://kubernetes.io/docs/tutorials/hello-minikube/) on getting started which could be useful to validate that your minikube is running correctly.

## Testing kubectl and helm

After installing `kubectl` and `helm` the following commands should run successfully on either a local or remote cluster.
Do not proceed unless `kubectl` and `helm` are working.

```shell
helm repo add examples https://helm.github.io/examples
helm install hello examples/hello-world
helm list
kubectl get pods
helm uninstall hello
```

#### Managing a Kubernetes cluster

The use of a k8s cluster management tool is highly recommended.
We like to use `k9s`: https://k9scli.io/

## Running

To get started first check you have all the necessary requirements:

> [!TIP]
> Don't forget to activate your python virtual environment when using new terminals!

```bash
warnet setup
```

Then create your first network:

```bash
# Create a new network in the current directory
warnet init

# Or in a directory of choice
warnet new <directory>
```

> [!TIP]
> If you are having stability issues it could be due to resource constraints. Check out these tips for [scaling](scaling.md).