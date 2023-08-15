from json import loads
import logging
from warnet.utils import exponential_backoff


logging.basicConfig(level=logging.INFO)

@exponential_backoff()
def bitcoin_rpc(container, command, params=None):
    """
    Run a Bitcoin RPC command in a given container.

    :param container: The Docker container in which to run the command
    :param command: The Bitcoin RPC command to run
    :param params: A list of parameters to pass to the command (default is None)
    :param verbose: Whether to print verbose output (default is False)
    :return: The result of the RPC command, or None if an error occurred
    """
    if params is None:
        params = []
    elif not isinstance(params, list):
        params = [params]

    command = 'bitcoin-cli ' + command + ' ' + ' '.join(map(str, params))

    logging.info(f"[bitcoin-cli]: {container.name}, {command:}")
    rcode, result = container.exec_run(command)

    if rcode in [0, None]:
        if result not in [None, "", b'']:
            return loads(result)
    else:
        raise Exception(result, rcode)

def getrawmempool(container):
    """
    Get the raw memory pool.

    :param container: The Docker container in which to run the command
    :return: The result of the getrawmempool RPC command
    """
    return bitcoin_rpc(container, 'getrawmempool')

def addnode(container, dest):
    """
    Add a node to the Bitcoin network.

    :param container: The Docker container in which to run the command
    :param dest: The destination node to add
    """
    bitcoin_rpc(container, 'addnode', [dest, 'add'])

def getpeerinfo(container):
    """
    Get information about the node's peers.

    :param container: The Docker container in which to run the command
    :return: The result of the getpeerinfo RPC command
    """
    return bitcoin_rpc(container, 'getpeerinfo')

def getnetworkinfo(container):
    """
    Get information about the node's network.

    :param container: The Docker container in which to run the command
    :return: The result of the getnetworkinfo RPC command
    """
    return bitcoin_rpc(container, 'getnetworkinfo')

def generatetoaddress(container, n, btc_address):
    """
    Generate blocks to a given address.

    :param container: The Docker container in which to run the command
    :param n: The number of blocks to generate
    :param btc_address: The Bitcoin address to which to generate the blocks
    :return: A list of block IDs
    """
    block_ids = bitcoin_rpc(container, 'generatetoaddress', [n, btc_address])

    block_ids = [str(block_id) for block_id in block_ids]
    return block_ids
