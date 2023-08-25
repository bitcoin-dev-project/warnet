import logging
from .test_node import TestNode
from .util import get_rpc_proxy
from warnet.warnet import Warnet

logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO
)

def setuptank(fmk):
    warnet = Warnet.from_docker_env("warnet")
    for i, tank in enumerate(warnet.tanks):
        ip = tank.ipv4
        logging.info(f"Adding TestNode {i} from {tank.bitcoind_name} with IP {ip}")
        node = TestNode(
            i,
            "", # datadir path
            chain=tank.bitcoin_network,
            rpchost=ip,
            timewait=60,
            timeout_factor=fmk.options.timeout_factor,
            bitcoind=None,
            bitcoin_cli=None,
            cwd=fmk.options.tmpdir,
            coverage_dir=fmk.options.coveragedir,
        )
        node.rpc = get_rpc_proxy(
            f"http://{tank.rpc_user}:{tank.rpc_password}@{ip}:{tank.rpc_port}",
            i,
            timeout=60,
            coveragedir=fmk.options.coveragedir,
        )
        node.rpc_connected = True
        fmk.nodes.append(node)
        fmk.num_nodes = len(fmk.nodes)
