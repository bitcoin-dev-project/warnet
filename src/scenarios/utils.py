def ensure_miner(node):
    wallets = node.listwallets()
    if "miner" not in wallets:
        node.createwallet("miner")
    return node.get_wallet_rpc("miner")
