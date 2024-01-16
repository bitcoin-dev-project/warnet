import random


def ensure_miner(node):
    wallets = node.listwallets()
    if "miner" not in wallets:
        node.createwallet("miner", descriptors=True)
    return node.get_wallet_rpc("miner")


# Assumes exponential distribution of block times
def next_block_delta(target_average_interval=600, max_interval=3600):
    delta = random.expovariate(1.0 / target_average_interval)
    return min(max_interval, delta)
