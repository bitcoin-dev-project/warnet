# Install Warnet

Warnet requires Kubernetes in order to run the network. Kubernetes can be run
remotely or locally (with minikube or Docker Desktop). `kubectl` must be run
locally to administer the network.

## Dependencies

### Kubernetes

Install [`kubectl`](https://kubernetes.io/docs/setup/) (or equivalent) and
configure your cluster. This can be done locally with `minikube` (or Docker Desktop)
or using a managed cluster.

#### Docker engine with minikube

If using Minikube to run a smaller-sized local cluster, you will require docker engine.
To install docker engine, see: https://docs.docker.com/engine/install/

e.g. For Ubuntu:

```bash
# First uninstall any old versions
for pkg in docker.io docker-doc podman-docker containerd runc; do sudo apt-get remove $pkg; done

# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add the repository to Apt sources:
echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

# Install the docker packages
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin
```

#### Using Docker

If you have never used Docker before you may need to take a few more steps to run the Docker daemon on your system.
The Docker daemon MUST be running before stating Warnet.

#### Managing Kubernetes cluster

The use of a k8s cluster management tool is highly recommended.
We like to use `k9s`: https://k9scli.io/

##### Linux

- [Check Docker user/group permissions](https://stackoverflow.com/a/48957722/1653320)
- or [`chmod` the Docker UNIX socket](https://stackoverflow.com/a/51362528/1653320)

## Install Warnet

### Recommended: use a virtual Python environment such as `venv`

```bash
python3 -m venv .venv # Use alternative venv manager if desired
source .venv/bin/activate
```

```bash
pip install --upgrade pip
pip install warnet
```

## Contributing / Local Warnet Development

### Download the code repository

```bash
git clone https://github.com/bitcoin-dev-project/warnet
cd warnet
```

### Recommended: use a virtual Python environment such as `venv`

```bash
python3 -m venv .venv # Use alternative venv manager if desired
source .venv/bin/activate
```

```bash
pip install --upgrade pip
pip install -e .
```

