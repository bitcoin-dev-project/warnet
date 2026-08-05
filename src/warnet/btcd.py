from .k8s import get_pod

_BTCD_CHAIN_FLAGS = {
    "regtest": "--regtest",
    "signet": "--signet",
    "testnet": "--testnet",
    "mainnet": "",
}


def get_btcd_rpc_info(tank: str, namespace: str) -> tuple[str, str, str, str]:
    """Return btcd RPC settings from the target pod metadata."""
    pod = get_pod(tank, namespace=namespace)
    labels = pod.metadata.labels or {}
    required_labels = ("chain", "RPCPort", "rpcuser", "rpcpassword")
    missing_labels = [label for label in required_labels if not labels.get(label)]
    if missing_labels:
        raise ValueError(f"Pod {tank} is missing required labels: {', '.join(missing_labels)}")

    chain = labels["chain"]
    try:
        chain_flag = _BTCD_CHAIN_FLAGS[chain]
    except KeyError as exc:
        raise ValueError(f"Unsupported btcd chain label: {chain}") from exc

    return chain_flag, labels["RPCPort"], labels["rpcuser"], labels["rpcpassword"]


def get_btcctl_flags(tank: str, namespace: str) -> str:
    chain_flag, rpc_port, rpc_user, rpc_pass = get_btcd_rpc_info(tank, namespace)
    return f"--rpcuser={rpc_user} --rpcpass={rpc_pass} --rpccert=/root/.btcd/rpc.cert --rpcserver=127.0.0.1:{rpc_port} {chain_flag}".strip()
