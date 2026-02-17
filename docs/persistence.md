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
    accessMode: ReadWriteOnce # optional, default is ReadWriteOnce
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
    accessMode: ReadWriteOnce # optional, default is ReadWriteOnce
```

## Existing PVCs

To use custom made PVC or PVC from previous deployment, use the `existingClaim` field to reference an existing PVC by name:

```yaml
persistence:
  enabled: true
  existingClaim: "bitcoin-node-001-data"
```

## Mount Paths

When persistence is enabled, the following directories are persisted in the PVCs:

- **Bitcoin Core:** `/root/.bitcoin/`
- **LND:** `/root/.lnd/`
- **CLN:** `/root/.lightning/`