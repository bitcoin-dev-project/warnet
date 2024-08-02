import os

from authproxy import AuthServiceProxy
from prometheus_client import Gauge, start_http_server


# Ensure that all RPC calls are made with brand new http connections
def auth_proxy_request(self, method, path, postdata):
    self._set_conn()  # creates new http client connection
    return self.oldrequest(method, path, postdata)


AuthServiceProxy.oldrequest = AuthServiceProxy._request
AuthServiceProxy._request = auth_proxy_request


# RPC Credentials for bitcoin node
# By default we assume the container is in the same pod as bitcoind, on regtest
BITCOIN_RPC_HOST = os.environ.get("BITCOIN_RPC_HOST", "localhost")
BITCOIN_RPC_PORT = os.environ.get("BITCOIN_RPC_PORT", "18443")
BITCOIN_RPC_USER = os.environ.get("BITCOIN_RPC_USER", "warnet_user")
BITCOIN_RPC_PASSWORD = os.environ.get("BITCOIN_RPC_PASSWORD", "2themoon")

# Port where prometheus server will scrape metrics data
METRICS_PORT = int(os.environ.get("METRICS_PORT", "9332"))

# Bitcoin Core RPC data to scrape. Expressed as labeled RPC queries separated by spaces
# label=method(params)[return object key][...]
METRICS = os.environ.get(
    "METRICS",
    'blocks=getblockcount() inbounds=getnetworkinfo()["connections_in"] outbounds=getnetworkinfo()["connections_in"] mempool_size=getmempoolinfo()["size"]',
)

# Set up bitcoind RPC client
rpc = AuthServiceProxy(
    service_url=f"http://{BITCOIN_RPC_USER}:{BITCOIN_RPC_PASSWORD}@{BITCOIN_RPC_HOST}:{BITCOIN_RPC_PORT}"
)


# Create closure outside the loop
def make_metric_function(cmd):
    try:
        return lambda: eval(f"rpc.{cmd}")
    except Exception:
        return None


# Parse RPC queries into metrics
commands = METRICS.split(" ")
for labeled_cmd in commands:
    if "=" not in labeled_cmd:
        continue
    label, cmd = labeled_cmd.strip().split("=")
    # label, description i.e. ("bitcoin_conn_in", "Number of connections in")
    metric = Gauge(label, cmd)
    metric.set_function(make_metric_function(cmd))
    print(f"Metric created: {labeled_cmd}")

# Start the server
server, thread = start_http_server(METRICS_PORT)

print(f"Server: {server}")
print(f"Thread: {thread}")

# Keep alive by waiting for endless loop to end
thread.join()
server.shutdown()
