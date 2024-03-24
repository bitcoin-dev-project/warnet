# Data Collection

## Bitcoin Core logs

Complete log output from a Bitcoin Core node can be retrieved by RPC `debug-log` using
its network name and graph node index.

Example:

```
$ warcli debug-log 0 --network=v25_test


2023-10-11T17:54:39.616974Z Bitcoin Core version v25.0.0 (release build)
2023-10-11T17:54:39.617209Z Using the 'arm_shani(1way,2way)' SHA256 implementation
2023-10-11T17:54:39.628852Z Default data directory /home/bitcoin/.bitcoin
... (etc)
```

## Aggregated logs from all nodes

Aggregated logs can be searched using RPC `grep-logs` with regex patterns.

Example:

```
$ warcli grep-logs 94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d

warnet_test_uhynisdj_tank_000001: 2023-10-11T17:44:48.716582Z [miner] AddToWallet 94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d  newupdate
warnet_test_uhynisdj_tank_000001: 2023-10-11T17:44:48.717787Z [miner] Submitting wtx 94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d to mempool for relay
warnet_test_uhynisdj_tank_000001: 2023-10-11T17:44:48.717929Z [validation] Enqueuing TransactionAddedToMempool: txid=94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d wtxid=0cc875e73bb0bd8f892b70b8d1e5154aab64daace8d571efac94c62b8c1da3cf
warnet_test_uhynisdj_tank_000001: 2023-10-11T17:44:48.718040Z [validation] TransactionAddedToMempool: txid=94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d wtxid=0cc875e73bb0bd8f892b70b8d1e5154aab64daace8d571efac94c62b8c1da3cf
warnet_test_uhynisdj_tank_000001: 2023-10-11T17:44:48.723017Z [miner] AddToWallet 94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d
warnet_test_uhynisdj_tank_000007: 2023-10-11T17:44:52.173199Z [validation] Enqueuing TransactionAddedToMempool: txid=94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d wtxid=0cc875e73bb0bd8f892b70b8d1e5154aab64daace8d571efac94c62b8c1da3cf
warnet_test_uhynisdj_tank_000007: 2023-10-11T17:44:52.173237Z [mempool] AcceptToMemoryPool: peer=0: accepted 94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d (poolsz 1 txn, 1 kB)
warnet_test_uhynisdj_tank_000007: 2023-10-11T17:44:52.173303Z [validation] TransactionAddedToMempool: txid=94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d wtxid=0cc875e73bb0bd8f892b70b8d1e5154aab64daace8d571efac94c62b8c1da3cf
warnet_test_uhynisdj_tank_000001: 2023-10-11T17:44:52.172963Z [mempool] Removed 94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d from set of unbroadcast txns
warnet_test_uhynisdj_tank_000002: 2023-10-11T17:44:52.325655Z [validation] Enqueuing TransactionAddedToMempool: txid=94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d wtxid=0cc875e73bb0bd8f892b70b8d1e5154aab64daace8d571efac94c62b8c1da3cf
warnet_test_uhynisdj_tank_000002: 2023-10-11T17:44:52.325691Z [mempool] AcceptToMemoryPool: peer=1: accepted 94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d (poolsz 1 txn, 1 kB)
warnet_test_uhynisdj_tank_000002: 2023-10-11T17:44:52.325838Z [validation] TransactionAddedToMempool: txid=94cacabc09b024b56dcbed9ccad15c90340c596e883159bcb5f1d2152997322d wtxid=0cc875e73bb0bd8f892b70b8d1e5154aab64daace8d571efac94c62b8c1da3cf
... (etc)
```
