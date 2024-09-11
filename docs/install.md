# Installing Warnet

Warnet requires Kubernetes (k8s) and helm in order to run the network. Kubernetes can be run remotely or locally (with minikube or Docker Desktop). `kubectl` and `helm` must be run locally to administer the network.

## Dependencies

### Remote (cloud) cluster

The only two dependencies of Warnet are `helm` and `kubectl` configured to talk to your cloud cluster.

### Running Warnet Locally

If the number of nodes you are running can run on one machine (think a dozen or so) then Warnet can happily run on a local Kubernetes. Two supported k8s implementations are Minikube and K8s as part of Docker Desktop.

#### Docker Desktop

[Docker desktop](https://www.docker.com/products/docker-desktop/) includes the docker engine itself and has an option to enable Kubernetes. Simply installing it and enabling Kubernetes should be enough.

[Helm](https://helm.sh/docs/intro/install/) is also required to be installed.

#### Minikube

Minikube requires a backend to run on with the supported backend being Docker. So if installing Minikube, you may need to install docker first. Please see [Installing Docker](https://docs.docker.com/engine/install/) and [Installing Minkube](https://minikube.sigs.k8s.io/docs/start/).

After installing Minikube don't forget to start it with:

```shell
minikube start
```

Minikube has a [guide](https://kubernetes.io/docs/tutorials/hello-minikube/) on getting started which could be useful to validate that your minikube is running correctly.

### Testing kubectl and helm

The following commands should run on both local and remote clusters. Do not proceed unless kubectl and helm are working.

```shell
helm repo add examples https://helm.github.io/examples
helm install hello examples/hello-world
helm list
kubectl get pods
helm uninstall hello
```

#### Managing Kubernetes cluster

The use of a k8s cluster management tool is highly recommended.
We like to use `k9s`: https://k9scli.io/

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

## Running

To get started first check you have all the necessary requirements:

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