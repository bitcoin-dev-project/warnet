# Tank Options

A *tank* is a Bitcoin Core node deployed inside the Kubernetes cluster. Each entry in the `nodes:` list of `network.yaml` defines one tank. All keys are optional unless marked required.

For how these values propagate from defaults through to Helm templates see [Configuration](config.md).

---

## `name` *(required)*

Pod name for this node. Must be unique within the network and follow Kubernetes naming rules (lowercase alphanumeric and hyphens).

```yaml
- name: tank-0000
```

Tanks are addressed by this name in `warnet bitcoin rpc <name>`, `warnet logs`, and scenario scripts (`self.tanks["tank-0000"]`).

---

## `addnode`

List of peer names this node will connect to on startup. Nodes are addressed by their `name` (for same-namespace peers) or by `<name>.default` for cross-namespace connections on the battlefield.

```yaml
addnode:
  - tank-0001
  - tank-0003
  - miner.default    # cross-namespace
```

---

## `image`

Docker image for the Bitcoin Core container.

```yaml
image:
  repository: bitcoindevproject/bitcoin   # default
  tag: "27.0"                             # required if not set in node-defaults.yaml
  pullPolicy: IfNotPresent
```

`tag` selects the Bitcoin Core version. Custom builds can be pulled from any repository:

```yaml
image:
  repository: myrepo/bitcoin-custom
  tag: "27.0-patch1"
```

---

## `config`

Additional lines appended to `bitcoin.conf` for this node only. Use this for per-node settings that differ from the defaults:

```yaml
config: |
  maxconnections=1000
  uacomment=tank-0000-red
  rpcauth=forkobserver:1418...
  rpcwhitelistdefault=0
```

> **Note:** Several options (`rpcuser`, `rpcpassword`, `rpcport`, ZMQ endpoints) are managed by the Helm chart and should not be set here. Use `global.rpcpassword` instead of `rpcpassword` in `config`.

---

## `global`

Sets the chain and RPC password for this node. These values are also shared with any Lightning sub-charts (LND/CLN) attached to the same pod.

```yaml
global:
  chain: signet        # regtest (default) | signet | mainnet
  rpcpassword: abc123  # unique per node recommended for large networks
```

Without this key the chart defaults to `regtest` with a shared password.

---

## `resources`

Standard Kubernetes [resource requests and limits](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/) for the Bitcoin Core container. Leave unset on resource-constrained local clusters.

```yaml
resources:
  limits:
    cpu: 4000m
    memory: 1000Mi
  requests:
    cpu: 100m
    memory: 200Mi
```

---

## `restartPolicy`

Kubernetes [pod restart policy](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#restart-policy). Default is `Never` — crashed tanks stay down, which is usually the desired behaviour for attack/test scenarios.

Set to `Always` when combined with `persistence` so the node recovers after cluster restarts.

```yaml
restartPolicy: Always
```

---

## `persistence`

Creates a Kubernetes Persistent Volume Claim for the node's data directory (`/root/.bitcoin/`). Without this, all chain data is lost when the pod is deleted.

```yaml
persistence:
  enabled: true
  size: 20Gi                   # default
  storageClass: ""             # uses cluster default
  accessMode: ReadWriteOncePod # use ReadWriteOnce for older k8s
  existingClaim: ""            # name of a pre-existing PVC to reuse
```

PVC names follow the pattern `<pod-name>.<namespace>-bitcoincore-data`.

---

## `startupProbe`

Overrides the default Kubernetes startup probe. Useful when a node needs custom initialisation before it is considered ready — for example, creating a wallet and importing a descriptor on a miner node:

```yaml
startupProbe:
  exec:
    command:
      - /bin/sh
      - -c
      - bitcoin-cli createwallet miner && bitcoin-cli importdescriptors [...]
  failureThreshold: 10
  periodSeconds: 30
  successThreshold: 1
  timeoutSeconds: 60
```

---

## `collectLogs`

When `true`, this node's Bitcoin Core logs are shipped to the Loki stack for aggregation in Grafana. The logging stack is installed automatically on first `warnet deploy` if any node has this set.

```yaml
collectLogs: true
```

---

## `metricsExport`

When `true`, attaches a `bitcoin-exporter` Prometheus sidecar to the pod that scrapes Bitcoin RPC results and exposes them on port `9332`. The Prometheus/Grafana stack is installed automatically.

```yaml
metricsExport: true
```

---

## `metrics`

Configures which RPC values the `bitcoin-exporter` sidecar collects. A space-separated list of `label=method(args)[json_key]` expressions:

```yaml
metrics: >
  blocks=getblockcount()
  mempool_size=getmempoolinfo()["size"]
  memused=getmemoryinfo()["locked"]["used"]
  memfree=getmemoryinfo()["locked"]["free"]
```

Default metrics (when `metricsExport: true` but no `metrics:` key) are block count, inbound peers, outbound peers, and mempool size.

---

## `prometheusMetricsPort`

Port the `bitcoin-exporter` sidecar listens on. Default is `9332`.

```yaml
prometheusMetricsPort: 9332
```

---

## `extraContainers`

List of additional sidecar containers to add to the tank pod. Each entry is a full Kubernetes container spec. This is the mechanism used internally by `metricsExport` to attach the `bitcoin-exporter` sidecar.

```yaml
extraContainers:
  - name: my-monitor
    image: myrepo/monitor:latest
    ports:
      - containerPort: 8080
        name: web
        protocol: TCP
    env:
      - name: TARGET
        value: "localhost:18443"
```

---

## `loadSnapshot`

Load a chain state snapshot from a URL at startup instead of syncing from genesis.

```yaml
loadSnapshot:
  enabled: true
  url: "https://example.com/snapshots/signet-height-50000.tar.gz"
```

---

## `ln`

Enables a Lightning Network node attached to this Bitcoin Core tank. The two implementations are mutually exclusive:

```yaml
ln:
  lnd: true   # enable LND
  cln: false  # enable CLN (default false)
```

When enabled, a second container is added to the pod and configured to connect to the local Bitcoin Core instance. See [LN Options](ln-options.md) for all configuration under the `lnd:` and `cln:` keys.

---

## `defaultConfig` and `baseConfig`

These keys are managed by Warnet and should not normally be set by users. `baseConfig` contains the chart's built-in defaults; `defaultConfig` is used by `warnet create` to inject project-level defaults. Both are overridden by `config`.
