# Data Persistence

By default, Warnet nodes use ephemeral storage, meaning all data is lost when a pod is deleted or restarted. This document describes how to enable persistent storage to be able to use warnet for persistent development environment, such that blockchain data, wallet information, and other node state can survive pod restarts and network redeployments. This is done with Kubernetes Persistent Volume Claims (PVCs), which persist independently of pod lifecycle.

Persistence is available for:
- **Bitcoin Core** nodes
- **LND** nodes
- **CLN** nodes

## Enabling Persistence

Persistence is configured per-node in the network graph definition. Add a `persistence` section to any node's configuration. This creates a new PVC for that node, which is then mounted to the appropriate data directory inside the container.

### Bitcoin Core Node

```yaml
bitcoin_core:
  image: bitcoincore-27.1:latest
  persistence:
    enabled: true
    size: 20Gi # optional, default is 20Gi
    storageClass: "" # optional, default is cluster default storage class
    accessMode: ReadWriteOncePod # optional, default is ReadWriteOncePod. For compatibility with older Kubernetes versions, you may need to set this to ReadWriteOnce
```

### Lightning Node

```yaml
<lnd or cln>:
  image:
    tag: <node-version-tag>
  persistence:
    enabled: true
    size: 10Gi # optional, default is 10Gi
    storageClass: "" # optional, default is cluster default storage class
    accessMode: ReadWriteOncePod # optional, default is ReadWriteOncePod. For compatibility with older Kubernetes versions, you may need to set this to ReadWriteOnce
```

## Existing PVCs

To use custom made PVC or PVC from previous deployment, use the `existingClaim` field to reference an existing PVC by name. If the network configuration or namespace did not change, there is no need to explicitly set the `existingClaim`. The existing PVC is used by default, since its generated name matches the default pattern. To explicitly use a PVC set the name like this:

```yaml
persistence:
  enabled: true
  existingClaim: "tank-0001.default-bitcoincore-data"
```

The generated PVC names follow the pattern:
`<pod-name>.<namespace>-<node-type>-data`

For example for a bitcoin core node:
`tank-0001.default-bitcoincore-data`

And for a LND node:
`tank-0001-ln.default-lnd-data`

Get the list of PVCs in the cluster with `kubectl get pvc -A` and delete any PVCs that are no longer needed with `kubectl delete pvc <pvc-name> -n <namespace>`.

## Mount Paths

When persistence is enabled, the following directories are persisted in the PVCs:

- **Bitcoin Core:** `/root/.bitcoin/`
- **LND:** `/root/.lnd/`
- **CLN:** `/root/.lightning/`