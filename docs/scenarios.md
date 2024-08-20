# Warnet Scenarios

Scenarios are written using the Bitcoin Core test framework for functional testing,
with some modifications: most notably that `self.nodes[]` represents an array of
containerized `bitcoind` nodes ("tanks"). Scenario files are run with a python interpreter
inside the server and can control many nodes in the network simultaneously.

See [`src/warnet/scenarios`](../src/warnet/scenarios) for examples of how these can be written.

To see available scenarios (loaded from the default directory):

```bash
warcli scenarios available
```

Once a scenario is selected it can be run with `warcli scenarios run [--network=warnet] <scenario_name> [scenario_params]`.

The [`miner_std`](../src/warnet/scenarios/miner_std.py) scenario is a good one to start with as it automates block generation:

```bash
# Have all nodes generate a block 5 seconds apart in a round-robin
warcli scenarios run miner_std --allnodes --interval=5
```

This will run the scenario in a background thread on the server until it exits or is stopped by the user.

Active scenarios can be listed and terminated by PID:

```bash
$ warcli scenarios available
miner_std      Generate blocks over time. Options: [--allnodes | --interval=<number> | --mature]
sens_relay     Send a transaction using sensitive relay
tx_flood       Generate 100 blocks with 100 TXs each

$ warcli scenarios run tx_flood
Running scenario tx_flood with PID 14683 in the background...

$ warcli scenarios active
      ┃ Active ┃ Cmd       ┃ Network ┃ Pid   ┃ Return_code ┃
      ┡━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━┩
      │ True   │ tx_flood  │ warnet  │ 14683 │ None        ┃

$ warcli scenarios stop 14683
Stopped scenario with PID 14683.
```

## Running a custom scenario

You can write your own scenario file locally and upload it to the server with
the [run-file](/docs/warcli.md#warcli-scenarios-run-file) command (example):

```bash
warcli scenarios run-file /home/me/bitcoin_attack.py
```
