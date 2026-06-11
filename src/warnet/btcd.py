from .k8s import get_pod

_BTCD_CHAIN_FLAGS = {
    "regtest": "--simnet",
    "signet": "--signet",
    "testnet": "--testnet",
    "mainnet": "",
}


def get_btcd_rpc_info(tank: str, namespace: str) -> tuple[str, str]:
    default_flag = "--simnet"
    default_port = "18334"
    try:
        pod = get_pod(tank, namespace=namespace)
        labels = pod.metadata.labels or {}
        chain = labels.get("chain", "regtest")
        rpc_port = labels.get("RPCPort", default_port)
        chain_flag = _BTCD_CHAIN_FLAGS.get(chain, default_flag)
        return chain_flag, rpc_port
    except Exception:
        return default_flag, default_port


def get_btcctl_flags(tank: str, namespace: str) -> str:
    chain_flag, rpc_port = get_btcd_rpc_info(tank, namespace)
    return f"--rpcuser=user --rpcpass=gn0cchi --rpccert=/root/.btcd/rpc.cert --rpcserver=127.0.0.1:{rpc_port} {chain_flag}".strip()
