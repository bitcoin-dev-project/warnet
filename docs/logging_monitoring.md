# Logging and Monitoring

Warnet allows different granularity of logging.

## Logging

### Warnet network level logging

Fetch logs from the warnet RPC server `rpc-0`, which is in charge of orchestrating the network.

Examples of information provided:

- how many tanks are running
- what scenarios are running
- warnet RPC requests

Commands: `warnet network logs` or `warnet network logs --follow`.

See more details in [warnet](/docs/warnet.md#warnet-network-logs)

### Bitcoin Core logs

These are tank level or pod level log output from a Bitcoin Core node, useful for things like net logging and transaction propagation, retrieved by RPC `debug-log` using its network name and graph node index.

Example:

```sh
$ warnet bitcoin debug-log 0


2023-10-11T17:54:39.616974Z Bitcoin Core version v25.0.0 (release build)
2023-10-11T17:54:39.617209Z Using the 'arm_shani(1way,2way)' SHA256 implementation
2023-10-11T17:54:39.628852Z Default data directory /home/bitcoin/.bitcoin
... (etc)
```

For logs of lightning nodes, kubectl is required.

### Aggregated logs from all nodes

Aggregated logs can be searched using `warnet bitcoin grep-logs` with regex patterns.

Example:

```sh
$ warnet bitcoin grep-logs 94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d

warnet_test_uhynisdj_tank_000001: 2023-10-11T17:44:48.716582Z [miner] AddToWallet 94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d  newupdate
warnet_test_uhynisdj_tank_000001: 2023-10-11T17:44:48.717787Z [miner] Submitting wtx 94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d to mempool for relay
warnet_test_uhynisdj_tank_000001: 2023-10-11T17:44:48.717929Z [validation] Enqueuing TransactionAddedToMempool: txid=94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d wtxid=0cc875e73bb0bd8f892b70b8d1e5154aab64daace8d571efac94c62b8c1da3cf
warnet_test_uhynisdj_tank_000001: 2023-10-11T17:44:48.718040Z [validation] TransactionAddedToMempool: txid=94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d wtxid=0cc875e73bb0bd8f892b70b8d1e5154aab64daace8d571efac94c62b8c1da3cf
warnet_test_uhynisdj_tank_000001: 2023-10-11T17:44:48.723017Z [miner] AddToWallet 94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d
warnet_test_uhynisdj_tank_000007: 2023-10-11T17:44:52.173199Z [validation] Enqueuing TransactionAddedToMempool: txid=94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d wtxid=0cc875e73bb0bd8f892b70b8d1e5154aab64daace8d571efac94c62b8c1da3cf
... (etc)
```

See more details in [warnet](/docs/warnet.md#warnet-bitcoin-grep-logs)

## Monitoring and Metrics

## Install logging infrastructure

Ensure that [`helm`](https://helm.sh/docs/intro/install/) is installed, then simply run the following scripts:

```bash
./resources/scripts/install_logging.sh
```

To forward port `3000` and view the [Grafana](#grafana) dashboard run the `connect_logging` script:

```bash
./resources/scripts/connect_logging.sh
```

It might take a couple minutes to get the pod running. If you see `error: unable to forward port because pod is not running. Current status=Pending`, hang tight.

The Grafana dashboard (and API) will be accessible without requiring authentication
at `http://localhost:3000`.

The `install_logging` script will need to be installed before starting the network in order to collect the information for monitoring and metrics. Restart the network with `warnet network down && warnet network up` if necessary.

### Prometheus

To monitor RPC return values over time, a Prometheus data exporter can be connected
to any Bitcoin Tank and configured to scrape any available RPC results.

The `bitcoin-exporter` image is defined in `resources/images/exporter` and
maintained in the BitcoinDevProject dockerhub organization. To add the exporter
in the Tank pod with Bitcoin Core add the `"exporter"` key to the node in the graphml file:

```xml
    <node id="0">
        <data key="version">27.0</data>
        <data key="exporter">true</data>
    </node>
```

The default metrics are defined in the `bitcoin-exporter` image:
- Block count
- Number of inbound peers
- Number of outbound peers
- Mempool size (# of TXs)

Metrics can be configured by setting a `"metrics"` key to the node in the graphml file.
The metrics value is a space-separated list of labels, RPC commands with arguments, and
JSON keys to resolve the desired data:

```
label=method(arguments)[JSON result key][...]
```

For example, the default metrics listed above are defined as:

```xml
    <node id="0">
        <data key="version">27.0</data>
        <data key="exporter">true</data>
        <data key="metrics">blocks=getblockcount() inbounds=getnetworkinfo()["connections_in"] outbounds=getnetworkinfo()["connections_in"] mempool_size=getmempoolinfo()["size"]</data>
    </node>
```

The data can be retrieved from the Prometheus exporter on port `9332`, example:

```
# HELP blocks getblockcount()
# TYPE blocks gauge
blocks 704.0
# HELP inbounds getnetworkinfo()["connections_in"]
# TYPE inbounds gauge
inbounds 0.0
# HELP outbounds getnetworkinfo()["connections_in"]
# TYPE outbounds gauge
outbounds 0.0
# HELP mempool_size getmempoolinfo()["size"]
# TYPE mempool_size gauge
mempool_size 0.0
```

### Grafana

Data from Prometheus exporters can be collected and fed into Grafana for a
web-based interface.

#### Dashboards

To view the default metrics in the included default dashboard, upload the dashboard
JSON file to the Grafana server:

```sh
curl localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  --data "{\"dashboard\": $(cat resources/configs/grafana/default_dashboard.json)}"
```

Note the URL in the reply from the server (example):

```sh
{"folderUid":"","id":2,"slug":"default-warnet-dashboard","status":"success","uid":"fdu0pda1z6a68b","url":"/d/fdu0pda1z6a68b/default-warnet-dashboard","version":1}(
```

Open the dashboard in your browser (example):

`http://localhost:3000/d/fdu0pda1z6a68b/default-warnet-dashboard`
