# Connecting Local Nodes

## Connections from cluster into local machine

[Telepresence](https://github.com/telepresenceio/telepresence) can be used to make a connection from the cluster to your local machine. Telepresence is designed to intercept cluster commmunication and forward it to your local machine so we will have to install a dummy pod and service to receive the traffic that will get forwarded.

### Run Warnet network

```shell
warnet deploy path/to/network/directory
```

### Install Telepresence

Install the open source version of Telepresence.

```shell
# find path to most recent release for your architecture and OS
# https://github.com/telepresenceio/telepresence/releases
wget [URL of release]
# assuming AMD64 linux binary (replace as needed)
sudo mv telepresence-linux-amd64 /usr/local/bin/telepresence
sudo chmod +x /usr/local/bin/telepresence
telepresence version
```

If on Mac OS you may need to remove telepresence from quarantine

```shell
sudo xattr -d com.apple.quarantine /usr/local/bin/telepresence
```

### Connect Telepresence to your cluster

```shell
telepresence helm install
telepresence connect
```

`telepresence version` should now show something like this:

```shell
OSS Client         : v2.19.1
OSS Root Daemon    : v2.19.1
OSS User Daemon    : v2.19.1
OSS Traffic Manager: v2.19.1
Traffic Agent      : docker.io/datawire/tel2:2.19.1
```

### Run a dummy pod and service to intercept

In this example we are installing a nginx pod but any image should work as the network traffic will not actually arrive at this pod and will instead be redirected to your local machine.

```shell
# Image here can be anything. Just picking a popular image.
kubectl create deploy local-bitcoind --image=registry.k8s.io/nginx
kubectl expose deploy local-bitcoind --port 18444 --target-port 18444
```

### Instruct Telepresence to intercept traffic to the dummy pod

The intercept command starts the process that will recieve the traffic. In this case, bitcoind process.

```shell
mkdir /tmp/connect
# Assumes you have bitcoind installed and available on the PATH
telepresence intercept local-bitcoind --port 18444 -- bitcoind --regtest --datadir=/tmp/connect
```

### Connect to local bitcoind from cluster

```shell
warnet bitcoin rpc 0 addnode "local-bitcoind:18444" "onetry"
# Check that the local node was added
warnet bitcoin rpc 0 getpeerinfo
```

### Disconnect and remove Telepresence

```shell
# Disconnect from the cluster
telepresence quit -s
# Remove Telepresence from the cluster
telepresent helm uninstall
# Remove Telepresence from your computer
sudo rm /usr/local/bin/telepresence
```
