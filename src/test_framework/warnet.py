import docker
import logging
from .test_node import TestNode
from .util import get_rpc_proxy

def setuptank(fmk):
    d = docker.from_env()
    network = d.networks.get("warnet")
    containers = [c for c in network.containers if "tank" in c.name]
    containers.sort(key=lambda c: c.name)
    fmk.num_nodes = len(containers)

    for i, c in enumerate(containers):
        ip = c.attrs['NetworkSettings']['Networks']["warnet"]['IPAddress']
        logging.info(f"Adding TestNode {i} named {c.name} with IP {ip}")
        node = TestNode(
            i,
            "", # datadir path
            chain="regtest",
            rpchost=str(ip),
            timewait=60,
            timeout_factor=fmk.options.timeout_factor,
            bitcoind=None,
            bitcoin_cli=None,
            cwd=fmk.options.tmpdir,
            coverage_dir=fmk.options.coveragedir,
        )
        node.rpc = get_rpc_proxy(
            f"http://btc:passwd@{ip}:18443",
            i,
            timeout=60,
            coveragedir=fmk.options.coveragedir,
        )
        node.rpc_connected = True
        fmk.nodes.append(node)




