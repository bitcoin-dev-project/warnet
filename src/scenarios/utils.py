from ipaddress import IPv4Address, IPv6Address, ip_address
from kubernetes import client, config


def ensure_miner(node):
    wallets = node.listwallets()
    if "miner" not in wallets:
        node.createwallet("miner", descriptors=True)
    return node.get_wallet_rpc("miner")


def get_service_ip(service_name: str) -> (IPv4Address | IPv6Address, IPv4Address | IPv6Address):
    """Given a service name and namespace, returns the service's external ip and internal ip"""
    # https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/V1Endpoints.md
    config.load_incluster_config()
    v1 = client.CoreV1Api()
    service = v1.read_namespaced_service(name=service_name, namespace="warnet")
    endpoints = v1.read_namespaced_endpoints(name=service_name, namespace="warnet")

    try:
        initial_subset = endpoints.subsets[0]
    except IndexError:
        raise f"{service_name}'s endpoint does not have an initial subset"
    try:
        initial_address = initial_subset.addresses[0]
    except IndexError:
        raise f"{service_name}'s initial subset does not have an initial address"

    return ip_address(service.spec.cluster_ip), ip_address(initial_address.ip)
