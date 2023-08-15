import docker
from .test_node import TestNode
from .util import get_rpc_proxy

class OPTIONS:
    nocleanup = True
    noshutdown = False
    cachedir = ""
    tmpdir = ""
    loglevel = "DEBUG"
    trace_rpc = None
    port_seed = 10000
    coveragedir = None
    descriptors = True
    timeout_factor = 1
    pdbonfailure = False
    usecli = False
    perf = False
    valgrind = False
    randomseed = 1

CONFIG = {
    "environment": {
        "BUILDDIR": "",
        "EXEEXT": "",
        "PACKAGE_BUGREPORT": ""
    }
}

def setupsandbox(fmk):
    d = docker.from_env()
    containers = [c for c in d.containers.list("all") if "warnet" in c.name]
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
            timeout_factor=OPTIONS.timeout_factor,
            bitcoind=None,
            bitcoin_cli=None,
            cwd=OPTIONS.tmpdir,
            coverage_dir=OPTIONS.coveragedir,
        )
        node.rpc = get_rpc_proxy(
            f"http://btc:passwd@{ip}:18443",
            i,
            timeout=60,
            coveragedir=OPTIONS.coveragedir,
        )
        node.rpc_connected = True
        fmk.nodes.append(node)




