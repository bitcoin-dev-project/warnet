from json import loads
from warnet.utils import exponential_backoff

@exponential_backoff()
def bitcoin_rpc(container, command, params=[], verbose=False):
    if not isinstance(params, list):
        params = [params]

    command = 'bitcoin-cli ' + command

    for param in params:
        command += ' ' + str(param)
    print(command)
    rcode, result = container.exec_run(command)

    if verbose:
        print("\t\t\t\t%s, %s" % (container.name, command))

    if rcode in [0, None]:
        if result not in [None, "", b'']:
            return loads(result)
    else:
        raise Exception(result, rcode)


def getrawmempool(container):
    return bitcoin_rpc(container, 'getrawmempool')


def addnode(container, dest):
    bitcoin_rpc(container, 'addnode', [dest, 'add'])


def getpeerinfo(container):
    return bitcoin_rpc(container, 'getpeerinfo')


def getnetworkinfo(container):
    return bitcoin_rpc(container, 'getnetworkinfo')


def generatetoaddress(container, n, btc_address):
    block_ids = bitcoin_rpc(container, 'generatetoaddress', [n, btc_address])

    # Cast unicode to str
    block_ids = [str(block_id) for block_id in block_ids]
    return block_ids
