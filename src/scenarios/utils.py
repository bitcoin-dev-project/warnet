import random
import math


def ensure_miner(node):
    wallets = node.listwallets()
    if "miner" not in wallets:
        node.createwallet("miner", descriptors=True)
    return node.get_wallet_rpc("miner")


# Assumes exponential distribution of block times
def next_block_delta(target_average_interval=600, max_interval=3600):
    delta = random.expovariate(1.0 / target_average_interval)
    return min(max_interval, delta)


# 150 blocks per halving in regtest
# 210000 blocks per halving in mainnet
def get_block_reward_sats(height, halvingBlocks=150):
    halvings = math.floor(height / halvingBlocks)
    if halvings >= 64:
        return 0
    reward = 50 * 100000000
    return reward >> halvings
