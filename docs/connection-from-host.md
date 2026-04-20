# Connection from host

### Using NodePort

To connect to a node from your host machine, you can use the NodePort service type. This exposes the node's desired ports on the host machine, allowing you to connect to them directly.

For example to connect to a Bitcoin Core node using the RPC port, add this to the node's configuration in the network graph definition:

```yaml
nodes:
  - name: tank-0001
    service:
      type: NodePort
      rpcNodePort: 30443
```

To get the IP address of a node in your cluster, execute `warnet host`:

```shell
# Minikube on Linux
> warnet host
192.168.49.2

# Docker Desktop on MacOS
> warnet host
kubernetes.docker.internal

# Remote cluster
> warnet host
159.223.123.163
```
Then you can connect to the NodePort in the cluster `<ip>:30443`.

> [!WARNING]
> If you are using MiniKube on MacOS, you must rely on `minikube service` to get both hostname and port for your tank:

```
(.venv) --> minikube service tank-0001
|-----------|-----------|-------------------------|---------------------------|
| NAMESPACE |   NAME    |       TARGET PORT       |            URL            |
|-----------|-----------|-------------------------|---------------------------|
| default   | tank-0001 | rpc/18443 p2p/18444     | http://192.168.49.2:30002 |
|           |           | zmq-tx/28333            | http://192.168.49.2:30984 |
|           |           | zmq-block/28332         | http://192.168.49.2:30682 |
|           |           | prometheus-metrics/9332 | http://192.168.49.2:30230 |
|           |           |                         | http://192.168.49.2:30175 |
|-----------|-----------|-------------------------|---------------------------|
🏃  Starting tunnel for service tank-0001.
|-----------|-----------|-------------|------------------------|
| NAMESPACE |   NAME    | TARGET PORT |          URL           |
|-----------|-----------|-------------|------------------------|
| default   | tank-0001 |             | http://127.0.0.1:62254 |
|           |           |             | http://127.0.0.1:62255 |
|           |           |             | http://127.0.0.1:62256 |
|           |           |             | http://127.0.0.1:62257 |
|           |           |             | http://127.0.0.1:62258 |
|-----------|-----------|-------------|------------------------|
[default tank-0001  http://127.0.0.1:62254
http://127.0.0.1:62255
http://127.0.0.1:62256
http://127.0.0.1:62257
http://127.0.0.1:62258]
❗  Because you are using a Docker driver on darwin, the terminal needs to be open to run it.
```




All the different port options can be seen in values.yaml files. The exposed port values must be in the range 30000-32767. If left empty, a random port in that range will be assigned by Kubernetes.

To check which ports are open on the host machine, use `kubectl get svc -n <namespace>` and look for the `PORT(S)` column.

### Using port-forward

Alternatively, you can use `kubectl port-forward` command. For example to expose the regtest RPC port of a Bitcoin Core node, run the command below. The first port is the local port on your machine, and the second port is the port inside the cluster. You can choose any available local port.

```shell
kubectl port-forward pod/tank-0001 18443:18443
```