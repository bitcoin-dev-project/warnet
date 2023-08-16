import docker
from .test_node import TestNode
from .util import get_rpc_proxy

def setuptank(fmk):
    d = docker.from_env()
    containers = [c for c in d.containers.list("all") if "warnet" in c.name]
    containers.sort(key=lambda c: c.name)
    fmk.num_nodes = len(containers)

    for i, c in enumerate(containers):
        ip = c.attrs['NetworkSettings']['Networks']["warnet_default"]['IPAddress']
        print(f"Adding TestNode {i} named {c.name} with IP {ip}")
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




