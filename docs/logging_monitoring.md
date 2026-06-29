# Logging and Monitoring

## Logging

### Pod logs

The command `warnet logs` will bring up a menu of pods to print log output from,
such as Bitcoin tanks, or scenario commanders. Follow the output with the `-f` option.

See command [`warnet logs`](/docs/warnet.md#warnet-logs)

### Bitcoin Core logs

Entire debug log files from a Bitcoin tank can be dumped by using the tank's
pod name.

Example:

```sh
$ warnet bitcoin debug-log tank-0000


2023-10-11T17:54:39.616974Z Bitcoin Core version v25.0.0 (release build)
2023-10-11T17:54:39.617209Z Using the 'arm_shani(1way,2way)' SHA256 implementation
2023-10-11T17:54:39.628852Z Default data directory /home/bitcoin/.bitcoin
... (etc)
```

See command [`warnet bitcoin debug-log`](/docs/warnet.md#warnet-bitcoin-debug-log)

### Aggregated logs from all Bitcoin nodes

Aggregated logs can be searched using `warnet bitcoin grep-logs` with regex patterns.

See more details in [`warnet bitcoin grep-logs`](/docs/warnet.md#warnet-bitcoin-grep-logs)

Example:

```sh
$ warnet bitcoin grep-logs 94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d

tank-0001: 2023-10-11T17:44:48.716582Z [miner] AddToWallet 94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d  newupdate
tank-0001: 2023-10-11T17:44:48.717787Z [miner] Submitting wtx 94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d to mempool for relay
tank-0001: 2023-10-11T17:44:48.717929Z [validation] Enqueuing TransactionAddedToMempool: txid=94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d wtxid=0cc875e73bb0bd8f892b70b8d1e5154aab64daace8d571efac94c62b8c1da3cf
tank-0001: 2023-10-11T17:44:48.718040Z [validation] TransactionAddedToMempool: txid=94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d wtxid=0cc875e73bb0bd8f892b70b8d1e5154aab64daace8d571efac94c62b8c1da3cf
tank-0001: 2023-10-11T17:44:48.723017Z [miner] AddToWallet 94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d
tank-0002: 2023-10-11T17:44:52.173199Z [validation] Enqueuing TransactionAddedToMempool: txid=94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d wtxid=0cc875e73bb0bd8f892b70b8d1e5154aab64daace8d571efac94c62b8c1da3cf
... (etc)
```


## Monitoring and Metrics

## Install logging infrastructure

If any tank in a network is configured with `collectLogs: true` or `metricsExport: true`
then the logging stack will be installed automatically when `warnet deploy` is executed.

The logging stack includes Loki, Prometheus, and Grafana. Together these programs
aggregate logs and data from Bitcoin RPC queries into a web-based dashboard.

## Connect to logging dashboard

The logging stack including the user interface web server runs inside the kubernetes cluster.
Warnet will forward port `2019` locally from the cluster, and the landing page for all
web based interfaces will be available at `localhost:2019`.

This page can also be opened quickly with the command [`warnet dashboard`](/docs/warnet.md#warnet-dashboard)


### Prometheus

To monitor RPC return values over time, a Prometheus data exporter can be connected
to any Bitcoin Tank and configured to scrape any available RPC results.

The `bitcoin-exporter` image is defined in `resources/images/exporter` and
maintained in the BitcoinDevProject dockerhub organization. To add the exporter
in the Tank pod with Bitcoin Core add the `metricsExport: true` value to the node in the yaml file.

The default metrics are defined in the `bitcoin-exporter` image:
- Block count
- Number of inbound peers
- Number of outbound peers
- Mempool size (# of TXs)

Metrics can be configured by setting an additional `metrics` value to the node in the yaml file. The metrics value is a space-separated list of labels, RPC commands with arguments, and
JSON keys to resolve the desired data:

```
label=method(arguments)[JSON result key][...]
```

For example, the default metrics listed above would be explicitly configured as follows:

```yaml
nodes:
  - name: tank-0000
    metricsExport: true
    metrics: blocks=getblockcount() inbounds=getnetworkinfo()["connections_in"] outbounds=getnetworkinfo()["connections_out"] mempool_size=getmempoolinfo()["size"]
```

The data can be retrieved directly from the Prometheus exporter container in the tank pod via port `9332`, example:

```
# HELP blocks getblockcount()
# TYPE blocks gauge
blocks 704.0
# HELP inbounds getnetworkinfo()["connections_in"]
# TYPE inbounds gauge
inbounds 0.0
# HELP outbounds getnetworkinfo()["connections_out"]
# TYPE outbounds gauge
outbounds 0.0
# HELP mempool_size getmempoolinfo()["size"]
# TYPE mempool_size gauge
mempool_size 0.0
```

### Defining lnd metrics to capture

Lightning nodes can also be configured to export metrics to Prometheus using `lnd-exporter`.
Example configuration is provided in `test/data/ln/`. Review `node-defaults.yaml` for a typical logging configuration. All default metrics reported to Prometheus are prefixed with `lnd_`.

[lnd-exporter configuration reference](https://github.com/bitcoin-dev-project/lnd-exporter/tree/main?tab=readme-ov-file#configuration)

The `lnd-exporter` sidecar is added via `lnd.extraContainers` and assumes the same macaroon referenced in `ln_framework` (can be overridden by environment variable). Enable metrics export and configure the scrape interval and port with these `lnd:` keys:

```yaml
nodes:
  - name: tank-0000
    ln:
      lnd: true
    lnd:
      metricsExport: true
      metricsScrapeInterval: 60s   # how often Prometheus scrapes (default: 15s)
      prometheusMetricsPort: 9332  # port the exporter listens on (default: 9332)
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
              value: 'lnd_block_height=parse("/v1/getinfo","block_height") pending_htlcs=PENDING_HTLCS'
          volumeMounts:
            - mountPath: /macaroon.hex
              name: config
              subPath: MACAROON_HEX
```

| Key | Description |
|-----|-------------|
| `lnd.metricsExport` | Set to `true` to enable Prometheus metrics scraping for this LND node |
| `lnd.metricsScrapeInterval` | How often Prometheus scrapes the exporter (e.g. `"60s"`, default `"15s"`) |
| `lnd.prometheusMetricsPort` | Port the `lnd-exporter` sidecar listens on (default `9332`) |
| `lnd.extraContainers` | List of additional sidecar containers to add to the LND pod (full Kubernetes container specs) |

**Note:** `test/data/ln` and `test/data/logging` use `lnd.extraContainers` to attach the `lnd-exporter` sidecar to the default `lnd/templates/pod`.

### Grafana

Data from Prometheus exporters is collected and fed into Grafana for a
web-based interface.

#### Dashboards

Grafana dashboards are described in JSON files. A default Warnet dashboard
is included and any other json files in the `/resources/charts/grafana-dashboards/files` directory
will also be deployed to the web server. The Grafana UI itself also has an API
for creating, exporting, and importing other dashboard files.
