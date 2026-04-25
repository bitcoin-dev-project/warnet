# LN Options

Lightning Network nodes are attached to Bitcoin Core tanks via the `ln:` key. Configuration specific to each implementation lives under a matching top-level key (`lnd:` or `cln:`).

Two implementations are available:

| Key | Implementation | Default image |
|-----|---------------|---------------|
| `ln.lnd: true` | [LND](https://github.com/lightningnetwork/lnd) by Lightning Labs | `lightninglabs/lnd:v0.20.1-beta` |
| `ln.cln: true` | [Core Lightning](https://github.com/ElementsProject/lightning) by Blockstream | `elementsproject/lightningd:v25.02` |

Only one implementation may be enabled per node.

```yaml
nodes:
  - name: tank-0000
    ln:
      lnd: true   # enable LND
    lnd:
      config: "color=#3399FF"
```

The LN container runs inside the same pod as Bitcoin Core and connects to it via localhost. The chain and RPC password are shared from `global.chain` and `global.rpcpassword` on the parent node — see [Tank Options](tank-options.md).

---

## LND options (`lnd:`)

### `image`

Docker image for the LND container. Override to pin a specific version:

```yaml
lnd:
  image:
    repository: lightninglabs/lnd   # default
    tag: "v0.18.2-beta"
    pullPolicy: IfNotPresent
```

---

### `config`

Additional lines appended to `lnd.conf`. Use this for per-node LND settings:

```yaml
lnd:
  config: |
    color=#e6194b
    bitcoin.timelockdelta=33
    ignore-historical-gossip-filters=true
```

Several options are managed by the chart (`rpclisten`, `bitcoind.rpcuser`, ZMQ endpoints, etc.) and should not be set here.

---

### `channels`

List of channels to open after the network is initialised. **You do not need to run anything manually** — `warnet deploy` detects channels in the network definition and automatically runs the `ln_init` scenario to set everything up.

```yaml
lnd:
  channels:
    - id:
        block: 500    # block height of the funding tx (must be unique across nodes)
        index: 1      # output index within that block (1-based, max 200 per block)
      target: tank-0001-ln   # pod name of the remote LND node (with -ln suffix)
      capacity: 1000000      # channel capacity in satoshis
      push_amt: 500000       # satoshis pushed to remote side on open (optional)
      source_policy:         # routing policy for outbound direction (optional)
        cltv_expiry_delta: 40
        htlc_minimum_msat: 1000
        fee_base_msat: 1000
        fee_proportional_millionths: 1
        htlc_maximum_msat: 990000000
      target_policy:         # routing policy for inbound direction (optional)
        cltv_expiry_delta: 40
        htlc_minimum_msat: 1000
        fee_base_msat: 1000
        fee_proportional_millionths: 1
        htlc_maximum_msat: 990000000
```

#### What `ln_init` does automatically

When `warnet deploy` finds any `lnd.channels` or `cln.channels` entry — in `network.yaml` or `node-defaults.yaml` — it runs `resources/scenarios/ln_init.py` as the final deploy step and streams its logs to the terminal. The full sequence is:

1. **Wait for L1 p2p** — holds until all Bitcoin Core nodes have established their connections from `addnode`.
2. **Mine to near channel-open height** — mines to block 496 (four blocks before the default `id.block` start of 500), building a usable chain. A node named `miner` is used as the block source; if none exists, the first node in the network is used instead.
3. **Fund LN wallets** — constructs a single transaction that sends 10 BTC UTXOs to the on-chain wallet of every node that opens at least one channel. These UTXOs are sized so that the change output always lands at tx output index 1, leaving the channel funding output at index 0 — which is what makes channel IDs deterministic.
4. **Establish LN p2p connections** — connects every channel pair directly, plus builds a ring through all LN nodes so the gossip graph is connected.
5. **Open channels block-by-block** — processes all channels sorted by `id.block`, then `id.index`. For each target block:
   - Mines to that height
   - Opens all channels assigned to that block in parallel, using decreasing fee rates so transactions land in the block in index order
   - Mines the block
   - **Asserts determinism**: verifies that `block_txs[id.index] == channel_txid` and the funding output is at index 0; aborts if not
6. **Mine 5 confirmation blocks** — waits for channels to reach the required confirmation depth.
7. **Wait for gossip sync** — polls every LN node until each one reports the full set of channels in its graph.
8. **Apply channel policies** — for any channel that defined `source_policy` or `target_policy`, sends an `UpdateChannelPolicy` to the respective node and waits for the policy to propagate across the network.

The terminal will stream `ln_init` log output during this process. On large networks it can take several minutes.

#### `id` constraints

The `id.block` and `id.index` values directly determine the [short channel ID](https://github.com/lightning/bolts/blob/master/07-routing-gossip.md#definition-of-short_channel_id) (SCID) that the channel will receive. Because SCIDs encode the funding transaction's block height and position, `ln_init` must place each funding transaction at *exactly* the right position in the mined chain.

Rules that must be followed across the entire network:

| Constraint | Value |
|------------|-------|
| Minimum `id.block` | `500` |
| Maximum channels per block (`id.index` range) | `200` (indices 1–200) |
| Indices within a block | Must be consecutive starting at `1` with no gaps |
| Global uniqueness | No two channels may share the same `block`/`index` pair |
| Channel capacity | Must be below ~4 BTC so the change output lands at tx index 1, not 0 |

Violating any of these causes `ln_init` to abort with an assertion error.

> **Tip:** When generating large networks programmatically, maintain a single global channel counter that increments `index` through 1–200 then increments `block`. See [Creating a Network](creating-a-network.md) for the fleet-script pattern.

#### Optional fields

| Field | Default | Notes |
|-------|---------|-------|
| `push_amt` | `0` | Satoshis pushed to the remote side on open; if omitted all funds start on the opener's side |
| `source_policy` | LND default | Routing policy applied to the outbound direction after the channel is confirmed |
| `target_policy` | LND default | Routing policy applied to the inbound direction; sent to the *target* node |

---

### `macaroonRootKey`

A base64-encoded root key used to derive all LND macaroons. Setting this ensures reproducible macaroons across deployments, which is required when the `adminMacaroon` must be known before the node starts (e.g. for pre-configured metric exporters or scenario scripts).

```yaml
lnd:
  macaroonRootKey: kjeST2GJccEZa0u9/5T3egyJjtZyDZ6UkHp3p1LzslU=
```

Generate with `lncli bakemacaroon --root_key=<hex>` or by deriving from random bytes with `base64.b64encode(os.urandom(32))`.

---

### `adminMacaroon`

A hex-encoded pre-baked admin macaroon. Use together with `macaroonRootKey` to make the node's admin macaroon known before deployment — useful for automating authentication in scenarios and sidecars.

```yaml
lnd:
  adminMacaroon: 0201036c6e6402f801...
```

---

### `resources`

Kubernetes resource requests and limits for the LND container:

```yaml
lnd:
  resources:
    limits:
      cpu: 2000m
      memory: 500Mi
    requests:
      cpu: 100m
      memory: 200Mi
```

---

### `restartPolicy`

Restart policy for the LND pod. Default is `Always`. Set to `Never` for vulnerable target nodes where you want the node to stay down after a crash:

```yaml
lnd:
  restartPolicy: Never
```

---

### `persistence`

Creates a PVC for the LND data directory (`/root/.lnd/`). PVC names follow the pattern `<pod-name>-ln.<namespace>-lnd-data`.

```yaml
lnd:
  persistence:
    enabled: true
    size: 10Gi
    storageClass: ""
    accessMode: ReadWriteOncePod
    existingClaim: ""
```

---

### `metricsExport`

When `true`, registers this node with the Prometheus/Grafana monitoring stack. Requires `extraContainers` to include an `lnd-exporter` sidecar that actually scrapes and exposes the metrics:

```yaml
lnd:
  metricsExport: true
  prometheusMetricsPort: 9332
  metricsScrapeInterval: 60s
```

---

### `metricsScrapeInterval`

How often Prometheus scrapes the LND metrics exporter. Default is `15s`.

```yaml
lnd:
  metricsScrapeInterval: 60s
```

---

### `prometheusMetricsPort`

Port the LND metrics exporter sidecar listens on. Default is `9332`.

```yaml
lnd:
  prometheusMetricsPort: 9332
```

---

### `extraContainers`

List of additional sidecar containers to add to the LND pod. The standard use is to attach the `lnd-exporter` Prometheus sidecar:

```yaml
lnd:
  extraContainers:
    - name: lnd-exporter
      image: bitcoindevproject/lnd-exporter:0.3.0
      imagePullPolicy: IfNotPresent
      ports:
        - containerPort: 9332
          name: prom-metrics
          protocol: TCP
      env:
        - name: METRICS
          value: >
            lnd_block_height=parse("/v1/getinfo","block_height")
            pending_htlcs=PENDING_HTLCS
            failed_payments=FAILED_PAYMENTS
      volumeMounts:
        - mountPath: /macaroon.hex
          name: config
          subPath: MACAROON_HEX
```

The `lnd-exporter` image reads the `METRICS` environment variable as a space-separated list of `label=expression` pairs. Built-in aggregated metrics (`PENDING_HTLCS`, `FAILED_PAYMENTS`) are provided by the exporter. REST API values are extracted with `parse("/v1/endpoint","json_key")`.

See the [lnd-exporter documentation](https://github.com/bitcoin-dev-project/lnd-exporter/tree/main?tab=readme-ov-file#configuration) for the full metric expression syntax.

---

### `circuitbreaker`

Deploys [Circuit Breaker](https://github.com/lightningequipment/circuitbreaker) as a sidecar alongside LND. Circuit Breaker is a Lightning Network firewall that limits in-flight HTLCs on a per-peer basis.

```yaml
lnd:
  circuitbreaker:
    enabled: true
    image: bitcoindevproject/circuitbreaker:v0.5.0   # optional, overrides default
    httpPort: 9235                                    # optional, overrides default
```

See [Circuit Breaker](circuit-breaker.md) for detailed usage.

---

## CLN options (`cln:`)

Core Lightning uses the same top-level structure. The `cln:` key mirrors `lnd:` for the options it shares:

| Key | Notes |
|-----|-------|
| `cln.image` | Same structure as `lnd.image` |
| `cln.config` | Lines appended to `config` (CLN config file format) |
| `cln.channels` | Same channel schema as LND |
| `cln.resources` | Same Kubernetes resource spec |
| `cln.persistence` | PVC at `/root/.lightning/`; default size 10Gi |
| `cln.extraContainers` | Same sidecar pattern |

CLN does not currently support `macaroonRootKey`, `adminMacaroon`, `metricsExport`, `metricsScrapeInterval`, `prometheusMetricsPort`, or `circuitbreaker`.
