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

Then you can connect to the node with `localhost:30443`. Or in non-local cluster `<kubernetes-cluster-ip>:30443`.

All the different port options can be seen in values.yaml files. The exposed port values must be in the range 30000-32767. If left empty, a random port in that range will be assigned by Kubernetes.

To check which ports are open on the host machine, use `kubectl get svc -n <namespace>` and look for the `PORT(S)` column.

### Using port-forward

Alternatively, you can use `kubectl port-forward` command. For example to expose the regtest RPC port of a Bitcoin Core node, run the below. The first port is the local port on your machine, and the second port is the port inside the cluster. You can choose any available local port.

```shell
kubectl port-forward pod/tank-0001 18443:18443
```