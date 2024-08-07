# Monitoring

## Prometheus

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

## Grafana

Data from Prometheus exporters can be collected and fed into Grafana for a
web-based interface.

### Install logging infrastructure

First make sure you have `helm` installed, then run the `install_logging` script:

```bash
resources/scripts/install_logging.sh
```

To forward port `3000` and view the Grafana dashboard run the `connect_logging` script:

```bash
resources/scripts/connect_logging.sh
```

The Grafana dashboard (and API) will be accessible without requiring authentication
at http://localhost:3000

## Dashboards

To view the default metrics in the included default dashboard, upload the dashboard
JSON file to the Grafana server:

```
curl localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  --data "{\"dashboard\": $(cat resources/configs/grafana/default_dashboard.json)}"
```

Note the URL in the reply from the server (example):

```
{"folderUid":"","id":2,"slug":"default-warnet-dashboard","status":"success","uid":"fdu0pda1z6a68b","url":"/d/fdu0pda1z6a68b/default-warnet-dashboard","version":1}(
```

Open the dashboard in your browser (example):

`http://localhost:3000/d/fdu0pda1z6a68b/default-warnet-dashboard`

