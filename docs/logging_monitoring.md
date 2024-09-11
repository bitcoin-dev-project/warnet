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
To access that from a local web browser, you must use kubernetes port-forwarding.

Run the script `./resources/scripts/connect_logging.sh` to forward port 3000.
The Grafana dashboard will then be available locally at `localhost:3000`.

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
    metrics: blocks=getblockcount() inbounds=getnetworkinfo()["connections_in"] outbounds=getnetworkinfo()["connections_in"] mempool_size=getmempoolinfo()["size"]
```

The data can be retrieved directly from the Prometheus exporter container in the tank pod via port `9332`, example:

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

Data from Prometheus exporters is collected and fed into Grafana for a
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
